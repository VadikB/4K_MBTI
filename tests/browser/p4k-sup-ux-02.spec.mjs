import { test, expect } from '@playwright/test';
import { readFile } from 'node:fs/promises';
import { startAdminProgramPreview } from '../../scripts/adm-program-ui-preview.mjs';

const release = (await readFile(new URL('../../web/js/config.js', import.meta.url), 'utf8'))
  .match(/APP_RELEASE = "([^"]+)";/)?.[1];
if (!release) throw new Error('web/js/config.js must define APP_RELEASE');

const published = [{ id: 11, name: 'Пилот 4К · 9 кейсов', version: '1.2' },
  { id: 12, name: 'Пилот 4К · 9 кейсов', version: '1.3' }];
const binding = (organizationId, id = 11) => ({
  organization_id: organizationId, program_definition_id: id, assignment_ref: 'pilot-4k',
  program_name: published.find((item) => item.id === id).name,
  program_version: published.find((item) => item.id === id).version, roles: [], role_capabilities: [],
});
const organization = (id, code, name, isActive, program, reports) => ({
  id, code, name, is_active: isActive, assessment_program: program,
  admins: [], members: [], domains: [], members_count: 0, reports_count: reports,
});
const card = (page) => page.locator('article[data-organization-id]');
const connect = (page) => card(page).locator('form[data-action="connect-assessment-program"]');
const status = (page) => page.locator('#admin-organizations-status');
const reference = process.env.P4K_UX02_REFERENCE_URL;
const operatorEmail = 'synthetic@example.test';
let preview;
test.beforeAll(async () => { preview = await startAdminProgramPreview({ port: 18963 }); });
test.afterAll(async () => { await preview?.close(); });

async function fixture(page, { superadmin = true } = {}) {
  const dashboard = { is_superadmin: superadmin, metrics: [], insights: [], activity_series: [], competency_average: [] };
  const items = [
    organization(4, 'sever', 'ООО «Север»', true, binding(4), 12),
    organization(3, 'vector', 'ООО «Вектор»', true, binding(3), 8),
    organization(5, 'liniya', 'АНО «Линия»', false, null, 3),
  ];
  items[0].admins = [{ user_id: 41, email: 'm.orlova@example.test', full_name: 'Марина Орлова', is_participant: true }];
  items[1].admins = [
    { user_id: 31, email: 'i.sokolov@example.test', full_name: 'Илья Соколов', is_participant: false },
    { user_id: 32, email: 'a.belova@example.test', full_name: 'Анна Белова', is_participant: true },
  ];
  items[2].admins = [{ user_id: 51, email: 'n.fomina@example.test', full_name: 'Нина Фомина' }];
  const state = { items, posts: [], puts: [], requests: [], createOutcome: 'success', failList: false, readback: null, problems: [{ organization_id: 4 }] };
  const listing = () => ({ is_superadmin: superadmin, items: superadmin ? items : items.slice(0, 1),
    assessment_programs: published, purge_preview_available: superadmin, physical_purge_available: false });
  await page.route('**/users/**', async (route) => {
    const request = route.request();
    const pathname = new URL(request.url()).pathname;
    const method = request.method();
    const json = (data, statusCode = 200) => route.fulfill({ json: data, status: statusCode });
    state.requests.push({ pathname, method });
    if (['/users/session/restore', '/users/18/session-bootstrap'].includes(pathname)) return json({
      authenticated: true, user: { id: 18, email: operatorEmail, full_name: 'Синтетический оператор' },
      is_admin: true, admin_dashboard: dashboard,
    });
    if (pathname === '/users/version') return json({ version: release });
    if (pathname === '/users/admin/dashboard') return json(dashboard);
    if (pathname === '/users/admin/support/preparation') return state.problems === null ? json({}, 503) : json({ items: state.problems, next_before: null });
    if (pathname === '/users/admin/organizations' && method === 'GET') return state.failList
      ? json({}, 503) : json(listing());
    if (pathname === '/users/admin/organizations' && method === 'POST') {
      const { name, code } = request.postDataJSON();
      state.posts.push({ name, code });
      if (state.createOutcome === 'duplicate' || items.some((item) => item.code === code)) return json({}, 409);
      items.push(organization(6, code, name, true, null, 0));
      return state.createOutcome === 'loss' ? route.abort('connectionreset') : json(listing());
    }
    const admins = pathname.match(/^\/users\/admin\/organizations\/(\d+)\/admins$/);
    if (admins && method === 'POST') {
      const org = items.find((item) => item.id === Number(admins[1]));
      const { email, full_name } = request.postDataJSON();
      org.admins.push({ user_id: 81, email, full_name, is_participant: false });
      return json(listing());
    }
    if (admins && method === 'DELETE') {
      const org = items.find((item) => item.id === Number(admins[1]));
      const email = new URL(request.url()).searchParams.get('email');
      org.admins = org.admins.filter((admin) => admin.email !== email);
      return json(listing());
    }
    if (pathname.endsWith('/questionnaire')) return json({ items: [] });
    const program = pathname.match(/^\/users\/admin\/organizations\/(\d+)\/assessment-program$/);
    if (program) {
      const organizationId = Number(program[1]);
      const item = items.find((org) => org.id === organizationId);
      if (method === 'PUT') {
        const request = route.request().postDataJSON();
        state.puts.push({ organizationId, ...request });
        item.assessment_program = binding(organizationId, request.program_definition_id);
        return json({ connection: item.assessment_program });
      }
      if (state.readback) return state.readback({ json, organizationId, item });
      return json({ connection: item.assessment_program });
    }
    return json({}, 404);
  });
  await page.goto(preview.base + '/demo/' + (superadmin ? 'superadmin' : 'admin') + '/confirmed/');
  if (superadmin) await page.locator('#admin-open-organizations-button').click();
  return state;
}

const open = (page, id) => page.locator('#platform-org-rows a[data-org-id="' + id + '"]:not([data-org-admins])').click();
const registry = (page) => page.locator('.platform-org-breadcrumb a').click();
const create = (page) => page.getByRole('link', { name: 'Создать организацию' }).click();

test('AC6 форма отклоняет собственную почту и принимает почту сотрудника после исправления', async ({ page }, info) => {
  const state = await fixture(page);
  await page.locator('#platform-org-rows a[data-org-id="4"][data-org-admins]').click();
  const form = page.locator('form[data-action="add-admin"]');
  const email = form.getByRole('textbox', { name: 'Рабочая почта' });
  const name = form.getByRole('textbox', { name: 'ФИО, если известно' });
  const submit = form.getByRole('button', { name: 'Добавить', exact: true });
  const error = form.getByRole('alert');
  const message = 'Вы вошли с этой почтой как суперадминистратор. Укажите рабочую почту другого сотрудника';
  const grants = () => state.requests.filter(({ method, pathname }) => method === 'POST' && pathname.endsWith('/admins'));
  await name.fill('Синтетический сотрудник');
  for (const address of [operatorEmail, operatorEmail.toUpperCase()]) {
    await email.fill(address);
    await submit.press('Enter');
    await expect(error).toHaveText(message);
    await expect(email).toHaveAttribute('aria-invalid', 'true');
    await expect(email).toHaveAccessibleDescription(message);
    await expect(email).toBeFocused();
    await expect(email).toHaveValue(address);
    await expect(name).toHaveValue('Синтетический сотрудник');
    await expect(submit).toBeEnabled();
    expect(grants()).toHaveLength(0);
  }
  for (const width of [1440, 390, 320]) {
    await page.setViewportSize({ width, height: width === 1440 ? 1000 : 844 });
    await expect(error).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(width);
    await page.evaluate(() => document.fonts.ready);
    await page.screenshot({ path: info.outputPath('ac6-own-email-' + width + '.png'), fullPage: true, scale: 'css' });
  }

  const colleagueEmail = 'colleague@example.test';
  await email.fill(colleagueEmail);
  await expect(error).toBeHidden();
  await expect(email).not.toHaveAttribute('aria-invalid', 'true');
  await expect(name).toHaveValue('Синтетический сотрудник');
  await submit.click();
  const administrators = page.locator('[data-organization-admins]');
  await expect(administrators.getByText(colleagueEmail)).toBeVisible();
  await expect(administrators.getByText('Администратор добавлен.')).toBeVisible();
  expect(grants()).toEqual([{ method: 'POST', pathname: '/users/admin/organizations/4/admins' }]);
});

test('UX-02 GET-only recovery uses exact code; duplicate is shown and admins are added from the card', async ({ page }) => {
  const state = await fixture(page);
  await create(page);
  const name = page.getByRole('textbox', { name: 'Название организации' });
  const code = page.getByRole('textbox', { name: 'Код организации' });
  await name.fill('ООО «Новая»');
  await code.fill('VECTOR');
  await page.getByRole('button', { name: 'Создать', exact: true }).click();
  await expect(status(page)).toContainText('с таким кодом уже существует');
  expect(state.posts).toHaveLength(0);
  await code.fill('NOVA');
  state.createOutcome = 'duplicate';
  await page.getByRole('button', { name: 'Создать', exact: true }).click();
  await expect(status(page)).toContainText('с таким кодом уже существует');
  await expect.poll(() => state.posts.length).toBe(1);
  state.createOutcome = 'loss';
  state.failList = true;
  await page.getByRole('button', { name: 'Создать', exact: true }).click();
  await expect(status(page)).toContainText('Исход создания пока неизвестен');
  await expect(code).toHaveValue('NOVA');
  expect(state.posts.at(-1)).toEqual({ name: 'ООО «Новая»', code: 'nova' });
  await expect(page.getByRole('button', { name: 'Проверить создание' })).toBeEnabled();
  state.failList = false;
  await page.reload();
  await expect(page.getByRole('button', { name: 'Проверить создание' })).toBeVisible();
  await page.getByRole('button', { name: 'Проверить создание' }).click();
  await expect(page).toHaveURL(/org=6/);
  await expect(status(page)).toContainText('Создание подтверждено по коду');
  await card(page).getByRole('link', { name: 'Управлять доступом' }).click();
  await expect(card(page).getByRole('heading', { name: 'Добавить администратора' })).toBeVisible();
  expect(state.posts).toHaveLength(2);
});

test('UX-02 ответ программы из прежней карточки не меняет новую карточку', async ({ page }) => {
  const state = await fixture(page);
  await open(page, 3);
  const reply = Promise.withResolvers();
  state.readback = async ({ json, item }) => {
    await reply.promise;
    return json({ connection: item.assessment_program });
  };
  try {
    await connect(page).locator('select').selectOption('12');
    await connect(page).getByRole('button', { name: 'Подключить', exact: true }).click();
    await expect.poll(() => state.requests.some((request) => request.method === 'GET' &&
      request.pathname === '/users/admin/organizations/3/assessment-program')).toBe(true);
    await registry(page);
    await open(page, 4);
    await expect(page.locator('#admin-organizations-title')).toHaveText('ООО «Север»');
    const received = page.waitForResponse((response) => response.request().method() === 'GET' &&
      response.url().endsWith('/3/assessment-program'));
    reply.resolve();
    await received;
    await expect(connect(page).locator('[data-program-connection-state] strong')).toHaveText('Пилот 4К · 9 кейсов · 1.2');
    await expect(connect(page).locator('[data-operation-status]')).toHaveCount(0);
    await registry(page);
    await expect(page.locator('#platform-org-rows [data-org-id="3"]:not([data-org-admins])').locator('xpath=ancestor::tr'))
      .toContainText('версия 1.3');
  } finally {
    reply.resolve();
  }
});

test('UX-02 FIX роль платформы не показывает формы анкеты после перезагрузки', async ({ page }) => {
  const state = await fixture(page);
  for (let visit = 0; visit < 2; visit += 1) {
    if (visit === 0) await open(page, 3);
    await expect(card(page).getByRole('heading', { name: 'Доступ к отчётам и анкете' })).toBeVisible();
    await expect(card(page).getByRole('button', { name: 'Анкета', exact: true })).toHaveCount(0);
    await expect(card(page).locator('[data-action="preview-early-data"], [data-action="preview-questionnaire"], [data-action="confirm-questionnaire"]')).toHaveCount(0);
    await expect(card(page)).toContainText('Анкету загружает администратор в своём кабинете.');
    await card(page).getByRole('link', { name: 'добавьте сотрудника вашей команды' }).click();
    await expect(card(page).getByRole('heading', { name: 'Добавить администратора' })).toBeFocused();
    await expect(page).toHaveURL(/org=3&view=admins/);
    await expect(card(page).getByRole('link', { name: 'Администраторы', exact: true })).toHaveAttribute('aria-current', 'page');
    if (visit === 0) {
      await page.reload();
      await expect(card(page).getByRole('heading', { name: 'Добавить администратора' })).toBeFocused();
      await card(page).getByRole('link', { name: 'Обзор' }).click();
    }
  }
  expect(state.requests.filter(({ pathname }) => pathname.includes('/questionnaire'))).toEqual([]);
});

test('UX-02 FIX счётчик отражает отказ, восстановление и подтверждённый ноль', async ({ page }) => {
  const state = await fixture(page);
  const row = page.getByRole('link', { name: /^Проблемы · ООО «Север»/u });
  const scope = '/?screen=admin-platform-problems&org=4';
  for (const [items, value] of [[state.problems, '1 проблема'], [null, '—'],
    [[{ organization_id: 4 }, { organization_id: 4 }], '2 проблемы'], [[], 'Нет проблем']]) {
    if (value !== '1 проблема') {
      state.problems = items;
      const read = page.waitForResponse((response) => response.url().endsWith('/support/preparation'));
      await page.locator('#admin-open-organizations-button').click();
      await read;
    }
    await expect(row).toHaveText(value);
    await expect(row).toHaveAttribute('href', scope);
    if (value === '—') await expect(row).toHaveAccessibleName(/Количество проблем недоступно/u);
    await open(page, 4);
    await expect(card(page).locator('[data-org-problem-count]')).toHaveText(value === '—' ? 'Количество проблем недоступно' : value);
    await expect(card(page).getByRole('link', { name: 'Открыть список' })).toHaveAttribute('href', scope);
  }
});

test('UX-FIX старые ссылки, отдельные разделы и безопасное повторное чтение реестра', async ({ page }) => {
  const state = await fixture(page);
  await page.goto(preview.base + '/?screen=admin-organizations&org=3&view=people');
  const navigation = page.getByRole('navigation', { name: 'Разделы организации' });
  const legacy = page.locator('[data-admin-view], [data-action="update-profile"], [data-action="add-domain"],' +
    ' [data-action="prepare-organization-assessments"], [data-action="add-member"], [data-action="import-members"]');
  await expect(navigation.getByRole('link', { name: 'Обзор' })).toHaveAttribute('aria-current', 'page');
  await expect(legacy).toHaveCount(0);
  await navigation.getByRole('link', { name: 'Администраторы' }).click();
  await expect(page).toHaveURL(/org=3&view=admins/u);
  await expect(connect(page)).toHaveCount(0);
  await expect(legacy).toHaveCount(0);
  await navigation.getByRole('link', { name: 'Журнал и операции' }).click();
  await expect(page).toHaveURL(/org=3&view=history/u);
  await expect(page.getByRole('heading', { name: 'Администраторы организации' })).toHaveCount(0);
  await expect(legacy).toHaveCount(0);
  await page.goBack();
  await expect(navigation.getByRole('link', { name: 'Администраторы' })).toHaveAttribute('aria-current', 'page');
  await page.goto(preview.base + '/?screen=admin-organizations&org=3#platform-org-admins-heading');
  await expect(page.getByRole('heading', { name: 'Администраторы организации' })).toBeFocused();
  await expect(page).toHaveURL(/org=3&view=admins/u);
  state.failList = true;
  await page.goto(preview.base + '/?screen=admin-organizations');
  await expect(page.locator('[data-organizations-stale]')).toContainText('Показано последнее подтверждённое состояние.');
  await expect(page.locator('#platform-org-count')).toHaveText('Найдено организаций: 3');
  await page.evaluate(() => { localStorage.clear(); sessionStorage.clear(); });
  await page.reload();
  await expect(page.locator('[data-organizations-stale]')).toBeVisible();
  await expect(page.locator('#platform-org-registry')).toBeHidden();
  state.failList = false;
  await page.getByRole('button', { name: 'Обновить безопасно' }).click();
  await expect(page.locator('#platform-org-count')).toHaveText('Найдено организаций: 3');
  await expect(page.locator('[data-organizations-stale]')).toHaveCount(0);
});

test('UX-02 FIX фон, подвал и заголовок создания на 320 px', async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 844 });
  await fixture(page);
  const footer = page.locator('.app-footer');
  for (const target of ['registry', 'create', 'card']) {
    if (target === 'registry') {
      await page.getByRole('searchbox', { name: 'Поиск организации' }).fill('нет совпадения');
    }
    if (target === 'create') await create(page);
    if (target === 'card') {
      await registry(page);
      await page.getByRole('searchbox', { name: 'Поиск организации' }).fill('');
      await open(page, 3);
    }
    const geometry = await footer.evaluate(node => ({
      bottom: Math.round(node.getBoundingClientRect().bottom + window.scrollY),
      viewport: innerHeight, height: document.documentElement.scrollHeight,
      width: document.documentElement.scrollWidth,
      color: getComputedStyle(document.querySelector('.admin-organizations-shell')).backgroundColor,
    }));
    expect(geometry.color).toBe('rgb(247, 247, 247)');
    expect(geometry.width).toBeLessThanOrEqual(320);
    expect(geometry.bottom).toBe(geometry.height);
    expect(geometry.bottom).toBeGreaterThanOrEqual(geometry.viewport);
    if (target === 'create') {
      const lines = await page.getByRole('heading', { name: 'Создать организацию' }).evaluate(node => {
        const range = document.createRange();
        range.selectNodeContents(node);
        return range.getClientRects().length;
      });
      expect(lines).toBe(1);
    }
  }
});

for (const width of [1440, 390, 320]) {
  test('UX-FIX отзыв последнего администратора на ' + width + ' px', async ({ page, context }, info) => {
    const viewport = { width, height: width === 1440 ? 1000 : 844 };
    await page.setViewportSize(viewport);
    const state = await fixture(page);
    const screenshot = async (target, label) => {
      await target.evaluate(() => document.fonts.ready);
      const footer = await target.locator('.app-footer').evaluate((node) => ({
        bottom: Math.round(node.getBoundingClientRect().bottom + scrollY),
        height: document.documentElement.scrollHeight,
        width: document.documentElement.scrollWidth,
      }));
      expect(footer.width).toBe(width);
      expect(footer.bottom).toBe(footer.height);
      await target.screenshot({ path: info.outputPath(label + '-' + width + '.png'), fullPage: true, scale: 'css' });
    };
    const account = page.locator('#admin-organizations-account-name');
    if (width === 1440) await expect(account.getByText('Суперадминистратор', { exact: true })).toBeVisible();
    await account.focus();
    await page.keyboard.press('Tab');
    await expect(page.locator('#admin-open-organizations-button')).toBeFocused();
    const count = page.getByRole('link', { name: /^Администраторы · ООО «Север»/u });
    await count.press('Enter');
    await expect(page).toHaveURL(/org=4&view=admins/u);
    await expect(page.getByRole('heading', { name: 'Администраторы организации' })).toBeFocused();
    await account.click();
    await expect(page.locator('#admin-organizations-menu-role')).toHaveText('Суперадминистратор платформы');
    await expect(page.locator('#admin-organizations-menu-name')).toHaveText('Синтетический оператор');
    await account.click();
    await screenshot(page, 'product-admins-single');
    const more = page.locator('.admin-access-row summary');
    const revoke = page.getByRole('menuitem', { name: 'Снять права', exact: true });
    const dialog = page.getByRole('dialog', { name: 'Снять права администратора?' });
    await more.press('Enter');
    await revoke.press('Enter');
    await expect(dialog.getByRole('button', { name: 'Отмена' })).toBeFocused();
    await expect(dialog).toContainText('Марина Орлова · m.orlova@example.test');
    await expect(dialog).toContainText('0 администраторов');
    await screenshot(page, 'product-admins-confirm');
    await page.keyboard.press('Escape');
    await expect(more).toBeFocused();
    expect(state.requests.filter(({ method }) => method === 'DELETE')).toHaveLength(0);
    await more.click();
    await revoke.click();
    await dialog.getByRole('button', { name: 'Снять права', exact: true }).click();
    await expect(card(page).getByText('Права администратора сняты.')).toBeVisible();
    await page.reload();
    await expect(page.getByText('Администраторов пока нет.')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Добавить', exact: true })).toBeEnabled();
    await screenshot(page, 'product-admins-empty');
    await registry(page);
    await expect(count).toHaveText('0');

    if (reference) {
      const demo = await context.newPage();
      await demo.setViewportSize(viewport);
      const url = reference + '/v1.6/?screen=admins&org=sever&view=screen';
      await demo.goto(url);
      await expect(demo.getByText('Марина Орлова', { exact: true })).toBeVisible();
      await screenshot(demo, 'reference-admins-single');
      // Keep the approved renderer intact and supply an empty synthetic list for the new state.
      await demo.goto(reference + '/v1.6/?screen=org-create&view=screen');
      await demo.locator('#org-new-name').fill('ООО «Проверка»');
      await demo.locator('#org-new-code').fill('UX_FIX');
      await demo.getByRole('button', { name: 'Создать', exact: true }).click();
      await demo.evaluate(() => {
        const key = 'p4k-superadmin-demo-organizations-v1.0';
        const records = JSON.parse(sessionStorage.getItem(key));
        records.find((item) => item.id === 'sever').admins = [];
        sessionStorage.setItem(key, JSON.stringify(records));
      });
      await demo.goto(url);
      await expect(demo.getByText('Администраторов пока нет.')).toBeVisible();
      await screenshot(demo, 'reference-admins-empty');
      await demo.close();
    }
  });

  test('UX-02 реестр, форма и состояния программы на ' + width + ' px', async ({ page, context }, info) => {
    const viewport = { width, height: width === 1440 ? 1000 : 844 };
    await page.setViewportSize(viewport);
    const state = await fixture(page);
    const query = page.getByRole('searchbox', { name: 'Поиск организации' });
    const capture = async (name) => {
      await page.evaluate(() => document.fonts.ready);
      const geometry = await page.locator('#admin-organizations-title').evaluate((element) => ({
        width: document.documentElement.scrollWidth, font: getComputedStyle(element).fontFamily,
        color: getComputedStyle(element).color,
      }));
      expect(geometry.width).toBeLessThanOrEqual(width);
      expect(geometry.font).toContain('Onest');
      expect(geometry.color).toBe('rgb(34, 44, 48)');
      if (['registry', 'empty', 'create', 'connected'].includes(name)) {
        const footer = page.locator('.app-footer');
        await expect(footer).toBeVisible();
        await expect(footer.locator('[data-app-release-number]')).toHaveText(release);
        await expect(footer.getByRole('link', { name: 'Согласие на обработку персональных данных' }))
          .toHaveAttribute('href', '/web/assets/docs/personal-data-consent.pdf');
        const layout = await footer.evaluate((node) => ({
          bottom: Math.round(node.getBoundingClientRect().bottom + scrollY),
          height: document.documentElement.scrollHeight,
          color: getComputedStyle(document.querySelector('.admin-organizations-shell')).backgroundColor,
        }));
        expect(layout.color).toBe('rgb(247, 247, 247)');
        expect(layout.bottom).toBe(layout.height);
        expect(layout.bottom).toBeGreaterThanOrEqual(viewport.height);
        if (name === 'create') await expect(page.locator('#admin-organizations-title')).toHaveCSS('font-size', width < 700 ? '24px' : '28px');
      }
      await page.screenshot({ path: info.outputPath('product-' + width + '-' + name + '.png'), fullPage: true, scale: 'css' });
    };
    await expect(page.locator('#platform-org-count')).toHaveText('Найдено организаций: 3');
    await expect(page.getByRole('link', { name: /^Проблемы · ООО «Север»/u })).toHaveText('1 проблема');
    await page.getByRole('link', { name: 'Создать организацию' }).focus();
    await page.keyboard.press('Tab');
    await expect(query).toBeFocused();
    await query.blur();
    await expect(query).toHaveCSS('height', '42px');
    await expect(page.getByRole('combobox', { name: 'Статус' })).toHaveCSS('height', '42px');
    await capture('registry');
    await query.fill('VECTOR');
    await expect(page.locator('#platform-org-count')).toHaveText('Найдено организаций: 1');
    await query.fill('север');
    await expect(page.locator('#platform-org-count')).toHaveText('Найдено организаций: 1');
    await query.fill('несуществующая');
    await expect(page.getByText('Организации не найдены')).toBeVisible();
    await capture('empty');
    await query.fill('');
    await page.getByRole('combobox', { name: 'Статус' }).selectOption('inactive');
    await expect(page.locator('#platform-org-count')).toHaveText('Найдено организаций: 1');
    await open(page, 5);
    await expect(page.locator('[data-platform-org-state]')).toHaveText('Неактивна');
    await expect(connect(page).getByRole('button', { name: 'Подключить' })).toHaveCount(0);
    await expect(card(page).getByRole('heading', { name: 'Добавить администратора' })).toHaveCount(0);
    await capture('inactive');
    await registry(page);
    await page.getByRole('combobox', { name: 'Статус' }).selectOption('');
    await create(page);
    await capture('create');
    await page.getByRole('textbox', { name: 'Название организации' }).fill('ООО «Пример»');
    await page.getByRole('textbox', { name: 'Код организации' }).fill('PRIMER');
    await page.getByRole('button', { name: 'Создать', exact: true }).click();
    await expect(card(page)).toContainText('Программа ещё не подключена');
    await capture('absent');
    await registry(page);
    await open(page, 3);
    await expect(card(page)).toContainText('Готовые отчёты: 8');
    await expect(connect(page)).toContainText('Пилот 4К · 9 кейсов · 1.2');
    await expect(connect(page).locator('option:checked')).toHaveText(/^Версия 1\.2 · /u);
    await capture('connected');
    await connect(page).locator('select').selectOption('12');
    state.readback = ({ json }) => json({}, 503);
    await connect(page).getByRole('button', { name: 'Подключить', exact: true }).click();
    await expect(connect(page)).toContainText('Чтение недоступно');
    await expect(connect(page).getByRole('button', { name: 'Подключить', exact: true })).toBeDisabled();
    await capture('unknown');
    expect(state.puts.at(-1)).toMatchObject({ organizationId: 3, program_definition_id: 12, operation_id: expect.any(String) });
    await page.reload();
    await expect(connect(page)).toContainText('пока не подтверждён');
    state.readback = ({ json }) => json({ connection: binding(3, 11) });
    await connect(page).getByRole('button', { name: 'Проверить состояние подключения' }).click();
    await expect(connect(page)).toContainText('Подключена другая версия');
    expect(state.puts).toHaveLength(1);
    await capture('other-version');

    if (reference) {
      const ref = await context.newPage();
      await ref.setViewportSize(viewport);
      const shot = async (name) => {
        await ref.evaluate(() => document.fonts.ready);
        await ref.screenshot({ path: info.outputPath('reference-' + width + '-' + name + '.png'), fullPage: true, scale: 'css' });
      };
      await ref.goto(reference + '/v1.6/?screen=organizations&view=screen');
      await expect(ref.locator('#org-query')).toBeVisible();
      await shot('registry');
      await ref.locator('#org-query').fill('несуществующая');
      await shot('empty');
      await ref.goto(reference + '/v1.6/?screen=organization&org=liniya&view=screen');
      await expect(ref.getByText('Программа не подключена', { exact: true })).toBeVisible();
      await shot('inactive');
      await ref.goto(reference + '/v1.6/?screen=org-create&view=screen');
      await expect(ref.locator('#org-new-name')).toBeVisible();
      await shot('create');
      await ref.locator('#org-new-name').fill('ООО «Пример»');
      await ref.locator('#org-new-code').fill('PRIMER');
      await ref.getByRole('button', { name: 'Создать', exact: true }).click();
      await expect(ref.getByText('Программа не подключена', { exact: true })).toBeVisible();
      await shot('absent');
      await ref.goto(reference + '/v1.6/?screen=organization&org=vector&view=screen');
      await expect(ref.getByText('Готовые отчёты:', { exact: false })).toBeVisible();
      await shot('connected');
      await ref.goto(reference + '/v1.6/practice/?screen=diagnostic&id=program');
      await expect(ref.getByRole('heading', { name: 'Исход подключения программы неизвестен' })).toBeVisible();
      await shot('unknown');
      await ref.goto(reference + '/admin-v3/index.html?scene=data');
      await shot('admin-data');
      await ref.close();
      const admin = await context.newPage();
      await admin.setViewportSize(viewport);
      await fixture(admin, { superadmin: false });
      await admin.getByRole('button', { name: 'Данные организации', exact: true }).click();
      expect(await admin.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
      await admin.screenshot({ path: info.outputPath('product-admin-data.png'), scale: 'css' });
      await admin.close();
    }
  });
}
