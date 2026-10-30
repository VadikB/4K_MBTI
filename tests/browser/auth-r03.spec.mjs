import { test, expect } from '@playwright/test';
import fs from 'node:fs/promises';
import http from 'node:http';
import path from 'node:path';

const root = process.cwd();
const port = 18764;
const base = `http://127.0.0.1:${port}`;
const appRelease = (await fs.readFile(path.join(root, 'web/js/config.js'), 'utf8'))
  .match(/APP_RELEASE = "([^"]+)";/)?.[1];
if (!appRelease) throw new Error('web/js/config.js must define APP_RELEASE');
let server;

test.beforeAll(async () => {
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
});

test.afterAll(async () => {
  await new Promise((resolve) => server.close(resolve));
});

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
    return fulfillJson(route, {}, 404);
  });
}

const adminUser = { id: 18, email: 'admin@example.test', full_name: 'Admin' };

async function adm28Preview(page) {
  await openAdminOrganizations(page, (route) => fulfillJson(route, { items: [] }), {
    ...adminOrganization, admins: [{ user_id: 18, email: adminUser.email, full_name: 'Admin' }],
  });
  const card = page.locator('[data-organization-id="3"]');
  await card.getByRole('button', { name: 'Данные организации', exact: true }).click();
  const form = card.locator('form[data-action="preview-early-data"]');
  let revisionId = 201;
  await page.route('**/users/admin/organizations/3/questionnaire/preview', (route) => {
    const payload = route.request().postDataJSON();
    return fulfillJson(route, { id: revisionId++, assignment_ref: payload.assignment_ref,
      status: 'ready_for_confirmation', channel: 'product_form', answers_json: payload.answers,
      validation_json: {}, participant_preview: { purpose: payload.answers.C02a.participant_text },
      recipient_options: ['participant', 'organization_admin'] });
  });
  await form.locator('[name="assignment_ref"]').fill('ADM28 synthetic');
  await form.locator('[name="source_author"]').fill('Synthetic owner');
  await form.locator('[name="purpose"]').fill('Synthetic purpose');
  await form.getByRole('button', { name: 'Сохранить черновик и предпросмотр' }).click();
  await expect(card.locator('.admin-questionnaire-preview')).toBeVisible();
  return { card, form, preview: card.locator('.admin-questionnaire-preview'),
    saved: { id: 201, assignment_ref: 'ADM28 synthetic', status: 'confirmed', channel: 'product_form',
      answers_json: { C02a: { participant_text: 'Synthetic purpose' } },
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
  await expect(card.locator('.admin-questionnaire-confirmation')).toContainText('Сведения подтверждены');
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
  await expect(preview.getByRole('button', { name: 'Подтвердить сведения' })).toBeDisabled();
  await card.getByRole('button', { name: 'Проверить результат' }).click();
  await expect(preview).toHaveCount(0);
  await expect(card.locator('.admin-questionnaire-confirmation')).toContainText('Сведения подтверждены');
  expect(posts).toBe(1);
});

test('ADM28 recipients stay checked and editable after navigation, and errors stay beside confirm', async ({ page }) => {
  const { card, preview } = await adm28Preview(page);
  const toggle = preview.locator('[name="questionnaire_recipient"][value="organization_admin"]');
  const recipient = preview.locator('[name="questionnaire_recipient_user"]');
  await toggle.check();
  await expect(preview.getByRole('button', { name: 'Подтвердить сведения' })).toBeDisabled();
  await preview.getByRole('button', { name: 'Подтвердить сведения' }).hover();
  await expect(preview.getByRole('button', { name: 'Подтвердить сведения' })).toHaveCSS('background-color', 'rgb(214, 226, 229)');
  await recipient.check();
  await preview.getByRole('button', { name: 'Подтвердить сведения' }).hover();
  await expect(preview.getByRole('button', { name: 'Подтвердить сведения' })).toHaveCSS('background-color', 'rgb(104, 119, 124)');
  await card.getByRole('button', { name: 'Организация и участники', exact: true }).click();
  await card.getByRole('button', { name: 'Данные организации', exact: true }).click();
  await expect(toggle).toBeChecked();
  await expect(recipient).toBeChecked();
  await expect(recipient).toBeEnabled();
  await page.route('**/users/admin/organizations/3/questionnaire/201/confirm', (route) =>
    fulfillJson(route, { detail: 'QUESTIONNAIRE_REVISION_CONFLICT' }, 409));
  await preview.getByRole('button', { name: 'Подтвердить сведения' }).click();
  await expect(preview.locator('[data-operation-status]')).toContainText('уже подтверждена более новая');
  await expect(preview.locator('[data-operation-status]')).toBeVisible();
  await expect(preview.getByRole('button', { name: 'Подтвердить сведения' })).toBeEnabled();
});

test('ADM28 old confirmation cannot delete a newly created preview or newer input', async ({ page }) => {
  const { card, preview, form, saved } = await adm28Preview(page);
  let release;
  const delayed = new Promise((resolve) => { release = resolve; });
  await page.route('**/users/admin/organizations/3/questionnaire/201/confirm', async (route) => {
    await delayed;
    return fulfillJson(route, saved);
  });
  await preview.getByRole('button', { name: 'Подтвердить сведения' }).click();
  await form.locator('[name="purpose"]').fill('New synthetic purpose');
  await form.getByRole('button', { name: 'Сохранить черновик и предпросмотр' }).click();
  await expect(card.locator('[data-questionnaire-revision-id="202"]')).toBeVisible();
  release();
  await expect(form.locator('[name="purpose"]')).toHaveValue('New synthetic purpose');
  await expect(card.locator('[data-questionnaire-revision-id="202"]')).toContainText('New synthetic purpose');
});

test('ADM28 late confirmation cannot replace another selected assessment', async ({ page }) => {
  const { card, preview, form, saved } = await adm28Preview(page);
  let release;
  const delayed = new Promise((resolve) => { release = resolve; });
  await page.route('**/users/admin/organizations/3/questionnaire/201/confirm', async (route) => {
    await delayed; return fulfillJson(route, saved);
  });
  await preview.getByRole('button', { name: 'Подтвердить сведения' }).click();
  await form.locator('[name="assignment_ref"]').fill('Another assessment');
  await form.locator('[name="assignment_ref"]').press('Tab');
  await form.locator('[name="purpose"]').fill('Another purpose');
  release();
  await expect(form.locator('[name="assignment_ref"]')).toHaveValue('Another assessment');
  await expect(form.locator('[name="purpose"]')).toHaveValue('Another purpose');
  await expect(card.locator('.admin-questionnaire-confirmation')).toHaveCount(0);
});

test('ADM28 late confirmation after account change cannot populate the new account', async ({ page }) => {
  const { preview, saved } = await adm28Preview(page);
  let release;
  const delayed = new Promise((resolve) => { release = resolve; });
  await page.route('**/users/admin/organizations/3/questionnaire/201/confirm', async (route) => {
    await delayed; return fulfillJson(route, saved);
  });
  await preview.getByRole('button', { name: 'Подтвердить сведения' }).click();
  await page.locator('#admin-organizations-logout-button').click();
  await expect(page.locator('#auth-panel')).toBeVisible();
  const nextUser = { ...adminUser, id: 28, email: 'next@example.test', full_name: 'Account B' };
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
  expect(questionnaires).toBe(1);
});

test('ADM28 temporary restore failure offers retry and does not show login credentials', async ({ page }) => {
  await page.route('**/users/session/restore', (route) => fulfillJson(route, { detail: 'unavailable' }, 503));
  await page.route('**/users/version', (route) => fulfillJson(route, {}, 503));
  await page.goto(base);
  await expect(page.locator('#session-restore-title')).toHaveText('Не удалось восстановить сессию');
  await expect(page.locator('#session-restore-retry')).toBeVisible();
  await expect(page.locator('#email-input')).toBeHidden();
  await expect(page.locator('.app-footer-release')).toHaveText(`Версия ${appRelease}`);
});

test('ADM28 initial HTML has a complete frontend version before JavaScript', async ({ browser }) => {
  const context = await browser.newContext({ javaScriptEnabled: false });
  try {
    const page = await context.newPage();
    await page.goto(base);
    await expect(page.locator('#session-restore-panel')).toBeVisible();
    await expect(page.locator('.app-footer-release')).toHaveText(`Версия ${appRelease}`);
    await expect(page.locator('#email-input')).toBeHidden();
  } finally { await context.close(); }
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

test('ADM28 superadmin still restores its global dashboard', async ({ page }) => {
  const dashboard = { is_superadmin: true, metrics: [], insights: [], activity_series: [], competency_average: [] };
  await page.route('**/users/**', (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === '/users/session/restore') return fulfillJson(route, {
      authenticated: true, user: adminUser, is_admin: true, admin_dashboard: dashboard,
    });
    if (path === '/users/admin/dashboard') return fulfillJson(route, dashboard);
    return fulfillJson(route, {});
  });
  await page.goto(base);
  await expect(page.locator('#admin-panel')).toBeVisible();
  await expect(page.locator('#admin-organizations-panel')).toBeHidden();
  await expect(page.locator('#admin-open-methodology-button')).toBeVisible();
});
const adminOrganization = {
  id: 3, code: 'r03', name: 'R03 Organization', is_active: true, domains: [], admins: [],
  members_count: 1, reports_count: 0,
  members: [{ user_id: 8, email: 'person@example.test', full_name: 'Person', has_password: false,
    registration_status: 'pending', invitation_id: 1, invitation_status: 'queued',
    invitation_delivery_status: 'queued', invitation_link_status: 'active' }],
};

async function openAdminOrganizations(page, invitationHandler, organization = adminOrganization, questionnaireResponse = null) {
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
      return fulfillJson(route, { is_superadmin: false, items: [organization] });
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
    if (pathname === '/users/admin/organizations/3/personal-invitations') return invitationHandler(route);
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

test('ARCH30 shows the current participant stage and keeps technical signals collapsed', async ({ page }) => {
  const baseMember = { ...adminOrganization.members[0], assessment_assignments: ['competencies_4k'] };
  const organization = {
    ...adminOrganization,
    members_count: 4,
    members: [
      { ...baseMember, user_id: 8, email: 'not-sent@example.test', invitation_delivery_status: 'not_sent' },
      { ...baseMember, user_id: 9, email: 'started@example.test', acquaintance_status: 'in_progress' },
      { ...baseMember, user_id: 10, email: 'preparing@example.test', assessment_preparation_status: 'running' },
      { ...baseMember, user_id: 11, email: 'failed@example.test', assessment_preparation_status: 'failed' },
    ],
  };
  await openAdminOrganizations(page, (route) => fulfillJson(route, { items: [] }), organization);
  const rows = page.locator('.admin-organization-member');
  await expect(rows.nth(0).locator('.admin-organization-current-stage')).toHaveText('Приглашение не отправлено');
  await expect(rows.nth(1).locator('.admin-organization-current-stage')).toHaveText('Проходит знакомство');
  await expect(rows.nth(2).locator('.admin-organization-current-stage')).toHaveText('Идёт подготовка оценки');
  await expect(rows.nth(3).locator('.admin-organization-current-stage')).toHaveText('Подготовка завершилась с ошибкой');
  await expect(rows.nth(0).locator('.admin-organization-invitation-state').first()).toBeHidden();
  await rows.nth(0).getByText('Подробности статуса').click();
  await expect(rows.nth(0).locator('.admin-organization-invitation-state')).toHaveCount(5);
  await expect(rows.nth(0).locator('.admin-organization-invitation-state').first()).toBeVisible();
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
  await expect(rows.first().locator('.admin-organization-invitation-state')).toHaveCount(5);
  await expect(rows.nth(1)).toContainText('Регистрация: завершена');
  await expect(rows.nth(1).locator('[data-action="send-member-invitation"]')).toHaveCount(0);

  // 683 CSS px approximates the available width at 200% browser zoom on a 1366 px display.
  for (const width of [320, 375, 390, 683, 768, 1024, 1366, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    const layout = await rows.first().evaluate((row) => {
      const main = row.querySelector('.admin-organization-member-main').getBoundingClientRect();
      const name = row.querySelector('strong').getBoundingClientRect();
      const statuses = row.querySelector('.admin-organization-member-statuses').getBoundingClientRect();
      const actions = row.querySelector('.admin-organization-member-actions').getBoundingClientRect();
      const select = row.querySelector('.admin-organization-member-select').getBoundingClientRect();
      const buttons = [...row.querySelectorAll('button')].map((button) => button.getBoundingClientRect());
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
    if (width >= 1100) {
      expect(layout.mainRight).toBeLessThanOrEqual(layout.statusesX);
      expect(layout.mainRight).toBeLessThanOrEqual(layout.actionsX);
    } else {
      expect(layout.statusesY).toBeGreaterThanOrEqual(layout.mainBottom);
      expect(layout.actionsY).toBeGreaterThanOrEqual(layout.mainBottom);
    }
  }

  const checkbox = rows.first().getByRole('checkbox', { name: 'Выбрать ' + longEmail });
  await checkbox.focus();
  await page.keyboard.press('Space');
  await expect(checkbox).toBeChecked();
  await rows.first().locator('.admin-organization-member-select').click();
  await expect(checkbox).not.toBeChecked();
  await page.getByRole('button', { name: 'Данные организации' }).click();
  await page.getByRole('button', { name: 'Организация и участники' }).click();
  await expect(rows.first().locator('[data-action="send-member-invitation"]')).toHaveAttribute('data-value', longEmail);
  page.once('dialog', async (dialog) => {
    expect(dialog.message()).toContain(longEmail);
    await dialog.dismiss();
  });
  await rows.first().locator('[data-action="delete-member"]').click();
});

test('ADM19-01 exposes three keyboard-operable management blocks without horizontal overflow', async ({ page }) => {
  await openAdminOrganizations(page, (route) => fulfillJson(route, { items: [] }));

  const card = page.locator('[data-organization-id="3"]');
  const people = card.locator('[data-admin-view="people"]');
  const organizationData = card.locator('[data-admin-view="organization-data"]');
  const questionnaire = card.locator('[data-admin-view="questionnaire"]');
  const peopleButton = card.getByRole('button', { name: 'Организация и участники' });
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

test('UX-FIX20-04 org-admin edits the attached card and never sees free tenant creation', async ({ page }) => {
  await openAdminOrganizations(page, (route) => fulfillJson(route, { items: [] }));
  await expect(page.locator('#admin-organization-create-form')).toBeHidden();
  const card = page.locator('[data-organization-id="3"]');
  await card.locator('.admin-organization-step[data-view="organization-data"]').click();
  const profile = card.locator('[data-action="update-profile"]');
  await expect(profile).toBeVisible();
  await expect(card).toHaveCSS('border-radius', '8px');
  await expect(profile).toHaveCSS('border-radius', '8px');
  await expect(card.locator('.admin-organization-member').first()).toHaveCSS('border-radius', '8px');
  let submitted;
  await page.route('**/users/admin/organizations/3', async (route) => {
    if (route.request().method() !== 'PATCH') return route.fallback();
    submitted = route.request().postDataJSON();
    return fulfillJson(route, { is_superadmin: false, items: [adminOrganization] });
  });
  await profile.locator('[name="name"]').fill('Закреплённая организация');
  await profile.locator('[name="code"]').fill('attached-org');
  await profile.getByRole('button', { name: 'Сохранить карточку' }).click();
  await expect.poll(() => submitted).toMatchObject({ name: 'Закреплённая организация', code: 'attached-org' });
});

test('UX-FIX20-04 keeps readiness separated when org-admin switches assessment', async ({ page }) => {
  const readiness = (status, message) => ({
    status: 'incomplete',
    early: { status, message },
    context: { status, message },
    roles: { status: 'not_started', message: 'Участники ещё не добавлены.', ready: 0, total: 0 },
    preparation: { status: 'idle', message: 'Активной подготовки сейчас нет.' },
  });
  await openAdminOrganizations(page, (route) => fulfillJson(route, { items: [] }), adminOrganization, {
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
  await assignment.fill('assessment-b');
  await assignment.blur();
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
  await expect(error).toContainText('temporary failure');
  await expect(error.getByRole('button', { name: 'Повторить' })).toBeVisible();
  await expect(card.locator('[data-admin-view="questionnaire"] .admin-readiness-panel'))
    .toContainText('Выберите оценку');
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
  await openAdminOrganizations(page, (route) => fulfillJson(route, { items: [] }), adminOrganization, {
    body: { items: [revision(31, 'A', 'Published A'), revision(32, 'B', 'Published B')] },
  });

  const card = page.locator('[data-organization-id="3"]');
  await card.getByRole('button', { name: 'Данные организации' }).click();
  const form = card.locator('[data-action="preview-early-data"]');
  await expect(form.locator('[name="purpose"]')).toHaveValue('Published A');
  await expect(form.locator('[name="source_author"]')).toHaveValue('Автор A');
  const assignment = form.locator('[name="assignment_ref"]');
  await assignment.focus();
  await assignment.fill('B');
  await assignment.press('Tab');
  await expect(form.locator('[name="purpose"]')).toHaveValue('Published B');
  await expect(form.locator('[name="organization_name"]')).toHaveValue('Организация B');
  await expect(form.locator('[name="source_author"]')).toHaveValue('Автор B');

  await form.locator('[name="purpose"]').fill('Draft B');
  await card.getByRole('button', { name: 'Участники' }).click();
  await card.getByRole('button', { name: 'Данные организации' }).click();
  await expect(form.locator('[name="purpose"]')).toHaveValue('Draft B');
});

test('UX-FIX20-02 preserves named drafts across all management views', async ({ page }) => {
  await openAdminOrganizations(page, (route) => fulfillJson(route, { items: [] }));
  const card = page.locator('[data-organization-id="3"]');
  const memberForm = card.locator('[data-action="add-member"]');
  await memberForm.locator('[name="email"]').fill('draft.member@example.test');
  await memberForm.locator('[name="full_name"]').fill('Черновик участника');
  await memberForm.locator('[name="role_description"]').fill('Черновик должности');
  await card.locator('input[name="invitation_email"]').check();

  await card.getByRole('button', { name: 'Данные организации' }).click();
  const earlyData = card.locator('[data-action="preview-early-data"]');
  await earlyData.locator('[name="assignment_ref"]').fill('Поток A');
  await earlyData.locator('[name="purpose"]').fill('Несохранённая цель A');

  await card.getByRole('button', { name: 'Анкета', exact: true }).click();
  const questionnaire = card.locator('[data-action="preview-questionnaire"]');
  await expect(questionnaire.locator('[name="assignment_ref"]')).toHaveValue('Поток A');
  await questionnaire.locator('[name="source_author"]').fill('Автор черновика');

  await card.getByRole('button', { name: 'Организация и участники' }).click();
  await expect(memberForm.locator('[name="email"]')).toHaveValue('draft.member@example.test');
  await expect(memberForm.locator('[name="full_name"]')).toHaveValue('Черновик участника');
  await expect(memberForm.locator('[name="role_description"]')).toHaveValue('Черновик должности');
  await expect(card.locator('input[name="invitation_email"]')).toBeChecked();

  await card.getByRole('button', { name: 'Данные организации' }).click();
  await expect(earlyData.locator('[name="assignment_ref"]')).toHaveValue('Поток A');
  await expect(earlyData.locator('[name="purpose"]')).toHaveValue('Несохранённая цель A');
  await card.getByRole('button', { name: 'Анкета', exact: true }).click();
  await expect(questionnaire.locator('[name="source_author"]')).toHaveValue('Автор черновика');

  const assignment = questionnaire.locator('[name="assignment_ref"]');
  await assignment.focus();
  await assignment.fill('Поток B');
  await assignment.press('Tab');
  await card.getByRole('button', { name: 'Организация и участники' }).click();
  await card.getByRole('button', { name: 'Анкета', exact: true }).click();
  await expect(questionnaire.locator('[name="source_author"]')).toHaveValue('');
  await questionnaire.locator('[name="source_author"]').fill('Автор B');
  await questionnaire.locator('[name="assignment_ref"]').focus();
  await questionnaire.locator('[name="assignment_ref"]').fill('Поток A');
  await questionnaire.locator('[name="assignment_ref"]').press('Tab');
  await card.getByRole('button', { name: 'Организация и участники' }).click();
  await card.getByRole('button', { name: 'Анкета', exact: true }).click();
  await expect(questionnaire.locator('[name="source_author"]')).toHaveValue('Автор черновика');
  await questionnaire.locator('[name="assignment_ref"]').focus();
  await questionnaire.locator('[name="assignment_ref"]').fill('Поток B');
  await questionnaire.locator('[name="assignment_ref"]').press('Tab');
  await card.getByRole('button', { name: 'Организация и участники' }).click();
  await card.getByRole('button', { name: 'Анкета', exact: true }).click();
  await expect(questionnaire.locator('[name="source_author"]')).toHaveValue('Автор B');
});

test('UX-FIX20-02 clears account A drafts and ignores its late preview after account B login', async ({ page }) => {
  let releasePreview;
  const previewReleased = new Promise((resolve) => { releasePreview = resolve; });
  await openAdminOrganizations(page, (route) => fulfillJson(route, { items: [] }));
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
    results_usage: 'Развитие', result_recipients: 'Участник', organizer: 'HR',
    responsible_contact: 'a@example.test', case_reality_level: 'Реальные', organization_name_usage_rules: 'Разрешено',
  };
  for (const [name, value] of Object.entries(valuesA)) await formA.locator(`[name="${name}"]`).fill(value);
  await formA.getByRole('button', { name: 'Сохранить черновик и предпросмотр' }).click();

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
  await expect(formB.locator('[name="assignment_ref"]')).toHaveValue('');

  releasePreview();
  await page.waitForTimeout(100);
  await expect(formB.locator('[name="purpose"]')).toHaveValue('');
  await expect(cardB.locator('.admin-questionnaire-preview')).toHaveCount(0);
});

test('UX-FIX20-02 keeps newer input when an older preview response arrives', async ({ page }) => {
  let releasePreview;
  const previewReleased = new Promise((resolve) => { releasePreview = resolve; });
  await openAdminOrganizations(page, (route) => fulfillJson(route, { items: [] }));
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
    results_usage: 'Развитие', result_recipients: 'Участник', organizer: 'HR',
    responsible_contact: 'hr@example.test', case_reality_level: 'Реальные', organization_name_usage_rules: 'Разрешено',
  };
  await form.locator('[name="assignment_ref"]').fill(values.assignment_ref);
  await form.locator('[name="assignment_ref"]').press('Tab');
  for (const [name, value] of Object.entries(values).filter(([name]) => name !== 'assignment_ref')) {
    await form.locator(`[name="${name}"]`).fill(value);
  }
  await form.getByRole('button', { name: 'Сохранить черновик и предпросмотр' }).click();
  await form.locator('[name="purpose"]').fill('Новая цель после отправки');
  releasePreview();
  const stalePreview = card.locator('.admin-questionnaire-preview');
  await expect(stalePreview).toBeVisible();
  await expect(form.locator('[name="purpose"]')).toHaveValue('Новая цель после отправки');
  await expect(stalePreview).toContainText('Обновите предпросмотр перед подтверждением');
  await expect(stalePreview.getByRole('button', { name: 'Подтвердить сведения' })).toBeDisabled();
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
  await page.getByRole('button', { name: 'Посмотреть результат' }).click();
  await expect(page.locator('#m8-report-chart svg')).toBeVisible();
  await page.locator('#participant-return-management-button').click();
  await expect(page.locator('#admin-organizations-panel')).toBeVisible();
});

test('ADM19-01 saves early organization data through the versioned product form contract', async ({ page }) => {
  await openAdminOrganizations(page, (route) => fulfillJson(route, { items: [] }));
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
    results_usage: 'Для индивидуального развития', result_recipients: 'Участник и HR',
    organizer: 'HR-команда', responsible_contact: 'hr@example.test',
    case_reality_level: 'Реалистичные рабочие ситуации', organization_name_usage_rules: 'Можно использовать название',
  };
  for (const [name, value] of Object.entries(values)) await form.locator(`[name="${name}"]`).fill(value);
  await form.getByRole('button', { name: 'Сохранить черновик и предпросмотр' }).click();

  await expect(card.locator('[data-admin-view="organization-data"] .admin-questionnaire-preview'))
    .toContainText('Готово к подтверждению');
  expect(submittedPayload.channel).toBe('product_form');
  expect(submittedPayload.csv_text).toBeNull();
  expect(submittedPayload.answers.C01).toEqual({
    name: values.organization_name, organization_type: values.organization_type,
    industry: values.industry, activity_description: values.activity_description,
  });
  expect(submittedPayload.answers.C21).toEqual({
    organizer: values.organizer, responsible_contact: values.responsible_contact,
  });
  expect(submittedPayload.idempotency_key).toBeTruthy();
});

test('UX-ADM28-01 changes recipients without invalidating content preview and applies confirmation immediately', async ({ page }) => {
  await openAdminOrganizations(page, (route) => fulfillJson(route, { items: [{ status: 'queued' }] }), {
    ...adminOrganization,
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
        result_recipients: payload.answers.C04.answer,
        organizer: payload.answers.C21.organizer,
        responsible_contact: payload.answers.C21.responsible_contact,
      },
      changes: [{ field: 'purpose', before: 'Старая цель', after: payload.answers.C02a.participant_text }],
      is_first_publication: false, recipient_options: ['participant', 'organization_admin'],
      recipient_projections: {
        participant: 'Результаты доступны только участнику.',
        organization_admin: 'Результаты доступны участнику и выбранным представителям заказчика.',
      },
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
    results_usage: 'Для развития', result_recipients: 'Участник', organizer: 'HR',
    responsible_contact: 'hr@example.test', case_reality_level: 'Реальные', organization_name_usage_rules: 'Разрешено',
  };
  for (const [name, value] of Object.entries(values)) await form.locator(`[name="${name}"]`).fill(value);
  await form.getByRole('button', { name: 'Сохранить черновик и предпросмотр' }).click();
  const preview = card.locator('[data-admin-view="organization-data"] .admin-questionnaire-preview');
  await expect(preview).toContainText('Что увидит участник');
  await expect(preview).toContainText('Новая цель участника');
  await expect(preview).toContainText('Старая цель');
  await expect(preview.locator('[data-questionnaire-recipient-projection]'))
    .toHaveText('Результаты доступны только участнику.');
  await preview.locator('[name="questionnaire_recipient"][value="organization_admin"]').check();
  await expect(preview.locator('[data-questionnaire-recipient-projection]'))
    .toHaveText('Результаты доступны только участнику.');
  await expect(preview).not.toContainText('Обновите предпросмотр перед подтверждением');
  await expect(preview).toContainText('Выберите хотя бы одного представителя заказчика');
  await expect(preview.getByRole('button', { name: 'Подтвердить сведения' })).toBeDisabled();
  await preview.locator('[name="questionnaire_recipient_user"]').first().check();
  await expect(preview.locator('[data-questionnaire-recipient-projection]'))
    .toHaveText('Результаты доступны участнику и выбранным представителям заказчика.');
  await expect(preview.getByRole('button', { name: 'Подтвердить сведения' })).toBeEnabled();
  await preview.getByRole('button', { name: 'Подтвердить сведения' }).click();
  await expect(preview).toHaveCount(0);
  await expect(card.locator('[data-admin-view="organization-data"] .admin-readiness-panel')).toContainText('Поток B');
  await expect(form.locator('[name="purpose"]')).toHaveValue('Новая цель участника');

});

test('F22-04 keeps a newer confirmed revision and input entered after confirm started', async ({ page }) => {
  let releaseConfirm;
  const confirmReleased = new Promise((resolve) => { releaseConfirm = resolve; });
  await openAdminOrganizations(page, (route) => fulfillJson(route, { items: [] }));
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
    results_usage: 'Развитие', result_recipients: 'Участник', organizer: 'HR',
    responsible_contact: 'hr@example.test', case_reality_level: 'Реальные', organization_name_usage_rules: 'Разрешено',
  };
  for (const [name, value] of Object.entries(values)) await form.locator(`[name="${name}"]`).fill(value);
  await form.getByRole('button', { name: 'Сохранить черновик и предпросмотр' }).click();
  await card.locator('.admin-questionnaire-preview').getByRole('button', { name: 'Подтвердить сведения' }).click();
  await form.locator('[name="purpose"]').fill('Draft after confirm');
  await card.getByRole('button', { name: 'Участники' }).click();
  await card.getByRole('button', { name: 'Данные организации' }).click();
  releaseConfirm();

  await expect(form.locator('[name="purpose"]')).toHaveValue('Draft after confirm');
  await expect(page.locator('#admin-organizations-status')).toContainText('более новая серверная редакция');
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
  const organization = {
    ...adminOrganization,
    members_count: 2,
    members: [
      { ...adminOrganization.members[0], user_id: 18, email: adminUser.email, full_name: 'Admin',
        registration_status: 'registered', assessment_assignments: [] },
      { ...adminOrganization.members[0], user_id: 19, email: 'colleague@example.test', full_name: 'Colleague',
        assessment_assignments: [] },
    ],
  };
  await openAdminOrganizations(page, (route) => fulfillJson(route, { items: [] }), organization);
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
  await page.getByRole('button', { name: 'Назначить оценку' }).click();
  await expect.poll(() => assignmentPayload).toBeTruthy();
  await expect(page.locator('#admin-organizations-status')).toContainText('Назначена: 2');
  expect(assignmentPayload.assignment_ref).toBe('competencies_4k');
  expect(assignmentPayload.user_ids.sort()).toEqual([18, 19]);
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
  await expect(card).toHaveCSS('border-color', 'rgb(214, 226, 229)');
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
  await expect(page.locator('#auth-panel .auth-external-brand')).toHaveText('4К Ассистент');
  await expect(page.locator('#auth-panel .auth-external-brand')).toBeVisible();
  await expect(page.locator('.app-footer-release')).toHaveText(`Версия ${appRelease}`);
  await expect(page.locator('.app-footer-release')).toBeVisible();
  await page.setViewportSize({ width: 360, height: 760 });
  await expect(page.locator('.app-footer-release')).toBeInViewport();
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
      action: 'continue', button_label: 'Продолжить', completed_cases: 0, total_cases: 4,
      calendar_deadline: '2026-10-19T15:30:00Z' }],
    completed_assessments: [{ cycle_id: 'cycle-ready', report_id: 'report-ready', title: 'Оценка 4К',
      organization_name: 'Организация', status: 'report_ready', status_label: 'Результат готов',
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
  await expect(page.getByText('Завершено ситуаций: 0 из 4')).toBeVisible();
  await expect(page.getByText('Завершить до 19 октября, 18:30 (МСК)')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Продолжить' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Посмотреть результат' })).toBeVisible();
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
    current: { cycle_id: 'cycle-rad01', report_id: 'report-rad01', report_revision_no: 1, results_revision_id: 'rr2', created_at: '2026-10-17T12:00:00Z', closed_at: '2026-10-17T11:00:00Z', role_ref: { name: 'Product Lead' } },
    previous: { cycle_id: 'cycle-previous', report_id: 'report-previous', report_revision_no: 1, results_revision_id: 'rr1', created_at: '2026-09-17T12:00:00Z', closed_at: '2026-09-17T11:00:00Z', role_ref: { name: 'Product Lead' } },
    skills: [
      { skill_id: 'K1.1', skill_name: 'Понимание собеседника', previous: 1.75, current: 2.25, difference: 0.5, comparability: { status: 'allowed', reason: null } },
      { skill_id: 'K1.2', skill_name: 'Ясность сообщения', previous: null, current: 2.25, difference: null, comparability: { status: 'not_allowed', reason: 'full_score_required' } },
    ],
  };
  await page.route('**/users/**', (route) => {
    const pathname = new URL(route.request().url()).pathname;
    if (pathname === '/users/version') return fulfillJson(route, { version: 'rad01-test' });
    if (pathname === '/users/session/restore') return fulfillJson(route, { authenticated: true, user, dashboard });
    if (pathname === '/users/8/journey-state') return fulfillJson(route, { next_action: 'show_dashboard', profile: { status: 'complete' }, onboarding: { status: 'completed' }, assessment: { status: 'report_ready' } });
    if (pathname === '/users/assessment/m8/reports/report-rad01') return fulfillJson(route, report);
    if (pathname === '/users/assessment/m8/history') return fulfillJson(route, { cycles: [
      { cycle_id: 'cycle-rad01', report_id: 'report-rad01', collection_closed_at: '2026-10-17T11:00:00Z' },
      { cycle_id: 'cycle-previous', report_id: 'report-previous', collection_closed_at: '2026-09-17T11:00:00Z' },
    ] });
    if (pathname === '/users/assessment/m8/reports/report-rad01/comparison') return fulfillJson(route, comparison);
    return fulfillJson(route, {}, 404);
  });
  await page.goto(base);
  await page.getByRole('button', { name: 'Посмотреть результат' }).click();
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
  await expect(page.locator('#m8-report-skills')).toContainText('По части проявлений');
  await expect(page.locator('#m8-report-chart-note')).toContainText('Пропуски оставлены открытыми');
  await page.getByRole('button', { name: 'Сравнить оценки' }).click();
  await expect(page.locator('.m8-comparison-table')).toContainText('0.5');
  await expect(page.locator('.m8-comparison-slices')).toContainText('нет полного результата');
  await expect(page.getByRole('link', { name: 'Скачать сравнение PDF' })).toHaveAttribute('href', /report-previous/);
  await page.getByRole('button', { name: 'Шкалы' }).click();
  await expect(page.locator('.m8-score-bars')).toBeVisible();
  await page.setViewportSize({ width: 360, height: 760 });
  await page.getByRole('button', { name: 'Заливка' }).click();
  await expect(page.locator('#m8-report-chart')).toBeHidden();
  await page.locator('#m8-report-tab-select').selectOption('K1');
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
  await page.getByRole('button', { name: 'Посмотреть результат' }).click();
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
  await page.getByRole('button', { name: 'Посмотреть результат' }).click();
  await page.evaluate(async () => { await document.fonts.ready; });

  // 683 CSS px approximates a 1366 px display at 200% browser zoom.
  for (const width of [320, 360, 375, 390, 430, 683]) {
    await page.setViewportSize({ width, height: 900 });
    for (let groupIndex = 0; groupIndex < groups.length; groupIndex += 1) {
      await page.locator('#m8-report-tab-select').selectOption(`K${groupIndex + 1}`);
      if (groupIndex === 3) {
        await expect(page.locator('.m8-chart-empty')).toBeVisible();
        await expect(page.locator('#m8-report-skills .report-skill-item')).toHaveCount(groups[groupIndex][1].length);
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
  await expect(page.locator('#m8-skill-S1-1')).toBeFocused();

  for (const width of [768, 1024, 1366, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    if (width <= 960) {
      await expect(page.locator('.m8-radar-key li')).toHaveCount(groups[0][1].length);
      await expect(page.locator('.m8-radar-label')).toHaveCount(0);
    } else {
      await expect(page.locator('.m8-radar-key')).toHaveCount(0);
      await expect(page.locator('.m8-radar-label')).toHaveCount(groups[0][1].length);
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
  await expect(page.locator('.m8-comparison-slices')).toContainText('нет полного результата');
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(false);
  await test.info().attach('qa19-04-mobile-radar', {
    body: await page.locator('#m8-report-chart').screenshot(), contentType: 'image/png',
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
  await expect(page.locator('#admin-organizations-status')).toContainText('В очереди: 1');
  await expect(page.locator('#admin-organizations-status')).not.toContainText('Почтовый сервис принял');
});

test('R03 network retry reuses invitation operation id', async ({ page }) => {
  const keys = [];
  await openAdminOrganizations(page, (route) => {
    keys.push(route.request().headers()['idempotency-key']);
    return route.abort('failed');
  });
  const button = page.locator('[data-action="send-member-invitation"]').first();
  await button.click();
  await expect(page.locator('#admin-organizations-status')).toContainText('Не удалось');
  await button.click();
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
  await expect(page.getByRole('button', { name: 'Проверить готовность' })).toBeVisible();
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

test('E02 falls back to journey polling when detailed Cycle status stalls', async ({ page }) => {
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
        next_action: 'show_processing', report_status: journeyReads > 1 ? 'ready' : 'not_ready',
        profile: { status: 'complete' }, onboarding: { status: 'completed' },
        assessment: { status: journeyReads > 1 ? 'report_ready' : 'analyzing', runtime_kind: 'cycle', cycle_id: 'slow-cycle' },
      });
    }
    if (pathname === '/users/assessment/m8/cycles/slow-cycle/status') {
      await new Promise((resolve) => setTimeout(resolve, 6000));
      return fulfillJson(route, { results_status: 'processing', report_status: 'not_created' });
    }
    return fulfillJson(route, {}, 404);
  });

  await page.goto(`${base}/?screen=processing`);
  await expect(page.locator('#processing-outcome-title')).toHaveText('Ваш результат готов', { timeout: 10000 });
  expect(journeyReads).toBeGreaterThan(1);
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
  await page.route('**/users/**', (route) => {
    const pathname = new URL(route.request().url()).pathname;
    if (pathname === '/users/version') return fulfillJson(route, { version: 'p03-test' });
    if (pathname === '/users/session/restore') return fulfillJson(route, { authenticated: true, user, is_admin: false, dashboard: {} });
    if (pathname === '/users/8/journey-state') return fulfillJson(route, {
      next_action: 'resume_assessment', profile: { status: 'complete' }, onboarding: { status: 'completed' },
      assessment: { status: 'in_progress', runtime_kind: 'cycle', cycle_id: 'cycle-p03', cycle_session_id: 'session-p03', assessment_situation_id: 'as-old' },
    });
    if (pathname === '/users/assessment/cycles/cycle-p03/runtime') return fulfillJson(route, {
      cycle_id: 'cycle-p03', status: { collection_status: 'active', remaining_seconds: 1200 },
      return_policy_enabled: true,
      current_situation: { assessment_situation_id: 'as-old', status: 'active', participant_payload: { title: 'Скрытая ситуация', content: 'Нельзя показывать до Continue' } },
      situations: [], plan: { plan: { route: [{}] } }, trace: { turns: [], events: [] },
    });
    if (pathname === '/users/assessment/m7/cycles/cycle-p03/presence') return fulfillJson(route, {
      cycle_id: 'cycle-p03', assessment_situation_id: 'as-old',
      heartbeat_interval_seconds: 30, presence_lease_seconds: 60,
    });
    if (pathname === '/users/assessment/m7/cycles/cycle-p03/return-state') return fulfillJson(route, {
      cycle_id: 'cycle-p03', position_no: 1, current_assessment_situation_id: 'as-old', current_assessment_situation_status: 'active',
      allowed_action: 'replace_current', recognized_absence_seconds: 180, remaining_seconds: 1200,
      calendar_deadline: '2026-10-18T12:00:00Z', progress: { completed_positions: 2, total_positions: 4 },
      provider_config_ref: null,
    });
    return fulfillJson(route, {}, 404);
  });
  await page.goto(`${base}/?screen=interview`);
  await expect(page.locator('.interview-return-card')).toBeVisible();
  await expect(page.getByText('Пройдено 2 из 4', { exact: false })).toBeVisible();
  await expect(page.getByText('Нельзя показывать до Continue')).toBeHidden();
  await expect(page.getByText('Календарный срок:', { exact: false })).toBeHidden();
  await expect(page.locator('#interview-timer-badge')).toContainText('Пауза');
  await expect(page.getByRole('button', { name: 'Продолжить', exact: true })).toBeVisible();
  await expect(page.locator('#interview-textarea')).toBeDisabled();
});

test('E01 renders accepted active assessment copy, colors and AS-scoped draft', async ({ page }) => {
  const user = { id: 8, email: 'person@example.test', full_name: 'Person' };
  await page.route('**/users/**', (route) => {
    const pathname = new URL(route.request().url()).pathname;
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
      cycle_id: 'cycle-e01', status: { collection_status: 'active', remaining_seconds: 2700 },
      return_policy_enabled: false,
      route: { positions: [{ position_no: 1, state: 'in_progress', current_assessment_situation_id: 'as-e01' }], progress: { total_positions: 3 } },
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
  await expect(page.getByRole('button', { name: 'Завершить ситуацию' })).toBeVisible();
  await expect(page.getByText('После отправки ответ нельзя изменить')).toBeVisible();
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
  await expect(page.getByRole('heading', { name: 'Данные для оценки готовятся' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Проверить готовность' })).toBeVisible();
  await expect(page.locator('#onboarding-panel')).toBeHidden();
  await page.getByRole('button', { name: 'Проверить готовность' }).click();
  await expect.poll(() => checks).toBeGreaterThan(1);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
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
  await page.getByRole('button', { name: 'Согласен и продолжить' }).click();
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
    prepared_plan: { cycle_id: 'cycle-r08', revision_id: 'revision-r08', revision_no: 1, plan: {
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
  await expect(page.locator('.onboarding-metrics')).toContainText('Время на выполнение');
  await expect(page.getByText('120 мин.')).toBeVisible();
  await expect(page.getByText('189 мин.')).toBeHidden();
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
  [403, 'Нет доступа к подготовке'], [409, 'Нужно обновить состояние назначения'],
  [503, 'Сервис подготовки временно недоступен'], ['network', 'Не удалось проверить подготовку'],
  ['failed', 'Не удалось подготовить оценку'], ['organization', 'Для оценки ещё нужны сведения организации'],
]) {
  test(`PATH29 readiness distinguishes ${failure} without a fake ready plan`, async ({ page }) => {
    const user = { id: 8, email: 'person@example.test', full_name: 'Synthetic' };
    const acquaintance = {
      readiness: { status: 'ready', organization_id: 10, assignment_ref: 'synthetic', questionnaire_revision_id: 1,
        responsible_contact: 'owner@example.test', briefing: { organizer: 'Synthetic', purpose: 'Synthetic',
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
    if (failure === 'organization') await expect(page.locator('#feature-list')).toContainText('owner@example.test');
    if (failure === 'failed') await expect(page.locator('#feature-list')).toContainText('synthetic-failed-operation');
  });
}
