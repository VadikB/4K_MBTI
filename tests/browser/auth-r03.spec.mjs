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
  expect(Math.round(passwordField.height)).toBe(49);
  await expect(page.locator('#auth-credential-step-indicator')).toHaveText('Шаг 1/2');
  const eyeImage = await page.locator('#auth-password-toggle-button').evaluate(
    (button) => getComputedStyle(button, '::after').backgroundImage,
  );
  expect(eyeImage).toMatch(/auth-eye\.svg/);
});
