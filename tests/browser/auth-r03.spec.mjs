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
    if (pathname === '/users/admin/organizations/3/questionnaire') {
      return fulfillJson(route, { items: [{ id: 11, assignment_ref: 'competencies_4k',
        status: 'confirmed', channel: 'product_form', validation_json: {}, briefing: {} }] });
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
  await page.route('**/users/**', (route) => {
    const pathname = new URL(route.request().url()).pathname;
    if (pathname === '/users/version') return fulfillJson(route, { version: 'rad01-test' });
    if (pathname === '/users/session/restore') return fulfillJson(route, { authenticated: true, user, dashboard });
    if (pathname === '/users/8/journey-state') return fulfillJson(route, { next_action: 'show_dashboard', profile: { status: 'complete' }, onboarding: { status: 'completed' }, assessment: { status: 'report_ready' } });
    if (pathname === '/users/assessment/m8/reports/report-rad01') return fulfillJson(route, report);
    return fulfillJson(route, {}, 404);
  });
  await page.goto(base);
  await page.getByRole('button', { name: 'Посмотреть результат' }).click();
  await expect(page.locator('#m8-report-chart svg')).toBeVisible();
  await expect(page.locator('.m8-radar-point')).toHaveCount(2);
  await expect(page.locator('.m8-radar-point.is-partial')).toHaveCount(1);
  await expect(page.locator('#m8-report-skills')).toContainText('По части проявлений');
  await expect(page.locator('#m8-report-chart-note')).toContainText('Пропуски оставлены открытыми');
  await page.getByRole('button', { name: 'Шкалы' }).click();
  await expect(page.locator('.m8-score-bars')).toBeVisible();
  await page.setViewportSize({ width: 360, height: 760 });
  await page.getByRole('button', { name: 'Заливка' }).click();
  await expect(page.locator('#m8-report-chart')).toBeHidden();
  await page.locator('#m8-report-tab-select').selectOption('K1');
  await expect(page.locator('#m8-report-chart svg')).toBeVisible();
  const layout = await page.evaluate(() => ({ scrollWidth: document.documentElement.scrollWidth, clientWidth: document.documentElement.clientWidth }));
  expect(layout.scrollWidth).toBe(layout.clientWidth);
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
    if (pathname === '/users/8/journey-state') return fulfillJson(route, {
      next_action: 'resume_assessment', profile: { status: 'complete' }, onboarding: { status: 'completed' },
      assessment: { status: 'in_progress', runtime_kind: 'cycle', cycle_id: 'cycle-e01', cycle_session_id: 'session-e01', assessment_situation_id: 'as-e01' },
    });
    if (pathname === '/users/assessment/cycles/cycle-e01/runtime') return fulfillJson(route, {
      cycle_id: 'cycle-e01', status: { collection_status: 'active', remaining_seconds: 2700 },
      return_policy_enabled: false,
      route: { positions: [{ position_no: 1, state: 'in_progress', current_assessment_situation_id: 'as-e01' }], progress: { total_positions: 3 } },
      current_situation: { assessment_situation_id: 'as-e01', status: 'active', participant_payload: { title: 'Разговор с коллегой', content: 'Обсудите изменение сроков' } },
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
  await expect(page.locator('.interview-message--situation')).toContainText('Обсудите изменение сроков');
  await expect(page.locator('#interview-scroll-area')).toHaveJSProperty('scrollTop', 0);
  await expect(page.getByRole('button', { name: 'Завершить ситуацию' })).toBeVisible();
  await expect(page.getByText('После отправки ответ нельзя изменить')).toBeVisible();
  await expect(page.locator('[data-speaker-label="Анна"]')).toBeVisible();
  await expect(page.locator('.interview-bubble.bot').first()).toHaveCSS('background-color', 'rgb(255, 255, 255)');

  await page.locator('#interview-textarea').fill('Мой незавершённый ответ');
  await page.reload();
  await expect(page.locator('#interview-textarea')).toHaveValue('Мой незавершённый ответ');
  await page.setViewportSize({ width: 375, height: 812 });
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
