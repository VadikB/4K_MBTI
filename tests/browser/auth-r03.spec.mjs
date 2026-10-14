import { test, expect } from '@playwright/test';
import fs from 'node:fs/promises';
import http from 'node:http';
import path from 'node:path';

const root = process.cwd();
const port = 18764;
const base = `http://127.0.0.1:${port}`;
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
const adminOrganization = {
  id: 3, code: 'r03', name: 'R03 Organization', is_active: true, domains: [], admins: [],
  members_count: 1, reports_count: 0,
  members: [{ user_id: 8, email: 'person@example.test', full_name: 'Person', has_password: false,
    registration_status: 'pending', invitation_id: 1, invitation_status: 'queued',
    invitation_delivery_status: 'queued', invitation_link_status: 'active' }],
};

async function openAdminOrganizations(page, invitationHandler) {
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
      return fulfillJson(route, { is_superadmin: false, items: [adminOrganization] });
    }
    if (pathname === '/users/admin/organizations/3/personal-invitations') return invitationHandler(route);
    return fulfillJson(route, {}, 404);
  });
  await page.goto(base);
  await page.locator('#email-input').fill(adminUser.email);
  await page.locator('#request-magic-link-button').click();
  await page.locator('#magic-token-input').fill('legacy-password');
  await page.locator('#verify-magic-link-button').click();
  await page.locator('#admin-open-organizations-button').click();
  await page.locator('input[name="invitation_email"]').waitFor();
}

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
  const passwordField = await page.locator('#magic-token-input').boundingBox();
  expect(Math.round(createCard.width)).toBe(502);
  expect(Math.round(createCard.height)).toBe(547);
  expect(Math.round(passwordField.height)).toBe(49);
  await expect(page.locator('#auth-credential-step-indicator')).toHaveText('Шаг 1 из 2');
  const eyeImage = await page.locator('#auth-password-toggle-button').evaluate(
    (button) => getComputedStyle(button, '::after').backgroundImage,
  );
  expect(eyeImage).toMatch(/auth-eye\.svg/);
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
