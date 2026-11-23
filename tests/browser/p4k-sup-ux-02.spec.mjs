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
let preview;
test.beforeAll(async () => { preview = await startAdminProgramPreview({ port: 18963 }); });
test.afterAll(async () => { await preview?.close(); });

async function fixture(page, { superadmin = true } = {}) {
  const dashboard = { is_superadmin: superadmin, metrics: [], insights: [], activity_series: [], competency_average: [] };
  const items = [
    organization(3, 'vector', 'ООО «Вектор»', true, binding(3), 8),
    organization(4, 'sever', 'ООО «Север»', true, binding(4), 12),
    organization(5, 'liniya', 'АНО «Линия»', false, null, 3),
  ];
  const state = { items, posts: [], puts: [], requests: [], createOutcome: 'success', failList: false, readback: null, problems: [{ organization_id: 4 }] };
  const listing = () => ({ is_superadmin: superadmin, items: superadmin ? items : items.slice(0, 1),
    assessment_programs: published });
  await page.route('**/users/**', async (route) => {
    const request = route.request();
    const pathname = new URL(request.url()).pathname;
    const method = request.method();
    const json = (data, statusCode = 200) => route.fulfill({ json: data, status: statusCode });
    state.requests.push({ pathname, method });
    if (['/users/session/restore', '/users/18/session-bootstrap'].includes(pathname)) return json({
      authenticated: true, user: { id: 18, email: 'synthetic@example.test', full_name: 'Синтетический оператор' },
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
  await open(page, 3);
  for (let visit = 0; visit < 2; visit += 1) {
    await expect(card(page).getByRole('heading', { name: 'Доступ к отчётам и анкете' })).toBeVisible();
    await expect(card(page).getByRole('button', { name: 'Анкета', exact: true })).toHaveCount(0);
    await expect(card(page).locator('[data-action="preview-early-data"], [data-action="preview-questionnaire"], [data-action="confirm-questionnaire"]')).toHaveCount(0);
    await expect(card(page)).toContainText('Анкету загружает администратор в своём кабинете.');
    await card(page).getByRole('link', { name: 'добавьте сотрудника вашей команды' }).click();
    await expect(card(page).getByRole('heading', { name: 'Добавить администратора' })).toBeFocused();
    if (visit === 0) await page.reload();
  }
  expect(state.requests.filter(({ method, pathname }) => method !== 'GET' && pathname.includes('/questionnaire'))).toEqual([]);
});

test('UX-02 FIX счётчик отражает отказ, восстановление и подтверждённый ноль', async ({ page }) => {
  const state = await fixture(page);
  const row = page.getByRole('link', { name: 'Проблемы · ООО «Север»' });
  const scope = '/?screen=admin-platform-problems&org=4';
  for (const [items, value] of [[state.problems, '1'], [null, '—'],
    [[{ organization_id: 4 }, { organization_id: 4 }], '2'], [[], '0']]) {
    if (value !== '1') {
      state.problems = items;
      const read = page.waitForResponse((response) => response.url().endsWith('/support/preparation'));
      await page.locator('#admin-open-organizations-button').click();
      await read;
    }
    await expect(row).toHaveText(value);
    await expect(row).toHaveAttribute('href', scope);
    await open(page, 4);
    await expect(card(page).locator('[data-org-problem-count]')).toHaveText(value);
    await expect(card(page).getByRole('link', { name: 'Открыть список' })).toHaveAttribute('href', scope);
  }
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
    if (target === 'card') expect(geometry.bottom).toBeGreaterThan(geometry.viewport);
    else expect(geometry.bottom).toBe(geometry.viewport);
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
        if (name === 'connected') expect(layout.bottom).toBeGreaterThan(viewport.height);
        else if (name !== 'registry' || width === 1440) expect(layout.bottom).toBe(viewport.height);
        if (name === 'create') await expect(page.locator('#admin-organizations-title')).toHaveCSS('font-size', width < 700 ? '24px' : '28px');
      }
      await page.screenshot({ path: info.outputPath('product-' + name + '.png'), fullPage: name === 'connected', scale: 'css' });
    };
    await expect(page.locator('#platform-org-count')).toHaveText('Найдено организаций: 3');
    await expect(page.getByRole('link', { name: 'Проблемы · ООО «Север»' })).toHaveText('1');
    await page.getByRole('link', { name: 'Создать организацию' }).focus();
    await page.keyboard.press('Tab');
    await expect(query).toBeFocused();
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
        await ref.screenshot({ path: info.outputPath('reference-' + name + '.png'), fullPage: name === 'connected', scale: 'css' });
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
