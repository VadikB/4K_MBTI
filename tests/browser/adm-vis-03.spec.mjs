import { expect, test } from '@playwright/test';
import { spawn, spawnSync } from 'node:child_process';
import { randomUUID } from 'node:crypto';
import { once } from 'node:events';
import { closeSync, mkdirSync, openSync, writeFileSync } from 'node:fs';
import path from 'node:path';

test('ADM-VIS-03 · Добавление, импорт, фильтр и пакетные действия в кабинете', async ({ page, context }, info) => {
  if (!process.env.STAND_ADMIN_URL) throw new Error('Explicit isolated STAND_ADMIN_URL required');
  const python = process.env.BROWSER_PYTHON || path.join(process.cwd(), '.venv/bin/python');
  const port = 18891;
  const base = 'http://127.0.0.1:' + port;
  const statePath = info.outputPath('state.json');
  const inputs = 'tests/path_admin_browser_inputs.py';
  mkdirSync(path.dirname(statePath), { recursive: true });
  const run = (file, action, options = []) => {
    const result = spawnSync(python, [file, action, '--state', statePath, ...options], { encoding: 'utf8', timeout: 45000 });
    if (result.status !== 0) throw new Error(action + ': ' + (result.error || result.stderr));
    return result.stdout.trim().split('\n').at(-1);
  };
  const cli = (action) => run('scripts/test_stand.py', action, ['--port', String(port)]);
  const requests = [];
  const errors = [];
  page.on('pageerror', (error) => errors.push(error.message));
  page.on('request', (request) => {
    if (request.method() === 'POST' && request.url().startsWith(base + '/users/admin/organizations/')) requests.push(request);
  });
  const post = (org, action) => page.waitForResponse((response) => response.request().method() === 'POST' &&
    response.url() === base + '/users/admin/organizations/' + org + '/' + action);

  let server;
  cli('create');
  try {
    cli('bootstrap');
    cli('seed');
    const fixture = JSON.parse(run(inputs, 'participants'));
    const log = openSync(info.outputPath('server.log'), 'w');
    server = spawn(python, [inputs, 'serve-participants', '--state', statePath], { stdio: ['ignore', log, log] });
    closeSync(log);
    await expect.poll(async () => (await fetch(base + '/health/ready').catch(() => null))?.status, { timeout: 30000 }).toBe(200);
    await context.addCookies([{ name: fixture.cookie_name, value: fixture.session, url: base }]);
    const id = fixture.organization_id;
    const emptyId = fixture.empty_organization_id;
    const picker = page.locator('#admin-organization-select');
    const card = (id) => page.locator('[data-organization-id="' + id + '"]');
    const list = (id) => card(id).locator('.admin-people-list');
    const row = (userId) => list(id).locator('[data-member-user-id="' + userId + '"]');
    const add = card(emptyId).locator('[data-action="add-member"]');
    const choose = (id) => picker.selectOption(String(id));
    const filter = (id) => list(id).locator('[data-action="toggle-appeals-filter"]');
    const action = (form) => list(id).locator('form[data-bulk-for="' + form + '"]');
    const geometry = [];

    await page.goto(base + '/?screen=admin-organizations');
    await choose(emptyId);
    await test.step('Пустой список, размеры, клавиатура и валидация', async () => {
      await expect(list(emptyId).getByRole('heading', { name: 'Участники', exact: true })).toBeVisible();
      await expect(list(emptyId)).toContainText('Участников пока нет');
      await expect(list(emptyId).getByRole('checkbox')).toHaveCount(0);
      await expect(list(emptyId).locator('[data-bulk-actions], .admin-assignment-readiness')).toHaveCount(0);
      await expect(add.locator('label span')).toHaveText(['Email', 'ФИО', 'Должность']);
      await expect(add.locator('input[placeholder], input[type="file"]')).toHaveCount(0);
      await expect(card(emptyId).getByLabel('Файл списка участников')).toBeHidden();
      await expect(filter(emptyId)).toHaveText('С обращениями');
      await filter(emptyId).focus();
      await page.keyboard.press('Space');
      await expect(filter(emptyId)).toHaveText('Все участники');
      await expect(filter(emptyId)).toHaveAttribute('aria-pressed', 'true');
      await expect(filter(emptyId)).toBeFocused();
      await expect(list(emptyId)).toContainText('Участников с обращениями нет');
      await page.keyboard.press('Enter');
      await expect(filter(emptyId)).toHaveAttribute('aria-pressed', 'false');

      for (const width of [1440, 390, 320]) {
        await page.setViewportSize({ width, height: 1000 });
        await expect(add).toBeVisible();
        await page.evaluate(() => document.fonts.ready);
        const sizes = await card(emptyId).evaluate((node) => {
          const list = node.querySelector('.admin-people-list').getBoundingClientRect();
          const form = node.querySelector('[data-action="add-member"]');
          const box = form.getBoundingClientRect();
          return {
            formWidth: box.width, listWidth: list.width, formHeight: box.height,
            desktopGap: box.left - list.right, stackedGap: box.top - list.bottom,
            inputHeight: form.querySelector('input').offsetHeight,
            buttonHeight: form.querySelector('button').offsetHeight,
            background: getComputedStyle(form).backgroundColor, font: getComputedStyle(form).fontFamily,
            scrollWidth: document.documentElement.scrollWidth, scale: visualViewport.scale, dpr: devicePixelRatio,
          };
        });
        expect(sizes).toMatchObject({ formHeight: width === 1440 ? 458 : 450, inputHeight: 56, buttonHeight: 48,
          background: 'rgb(255, 255, 255)', scrollWidth: width, scale: 1, dpr: 1 });
        expect(sizes.font).toContain('Onest');
        if (width === 1440) expect(sizes).toMatchObject({ formWidth: 254, listWidth: 806, desktopGap: 20 });
        else expect(sizes).toMatchObject({ formWidth: width - 28, listWidth: width - 28, stackedGap: 20 });
        geometry.push({ width, ...sizes });
      }
      for (const label of ['Email', 'ФИО', 'Должность']) await expect(add.getByLabel(label)).toHaveValue('');
      const email = add.getByLabel('Email');
      const name = add.getByLabel('ФИО');
      const position = add.getByLabel('Должность');
      const submit = add.getByRole('button', { name: 'Добавить', exact: true });
      await email.fill('некорректно');
      await page.keyboard.press('Tab');
      await expect(name).toBeFocused();
      await name.fill('Синтетический аналитик');
      await page.keyboard.press('Tab');
      await expect(position).toBeFocused();
      await position.fill('Аналитик');
      await page.keyboard.press('Tab');
      await expect(submit).toBeFocused();
      await page.keyboard.press('Enter');
      await expect(email).toBeFocused();
      expect(requests).toHaveLength(0);
      await email.fill('manual-adm-vis-03@example.test');
      const added = post(emptyId, 'members');
      await submit.press('Enter');
      expect((await added).status()).toBe(200);
      await expect(list(emptyId).getByRole('button', { name: 'Синтетический аналитик', exact: true })).toBeVisible();
      await expect(list(emptyId).locator('.admin-organization-member')).toHaveCount(1);
      await expect(email).toHaveValue('');
      await expect(list(emptyId).locator('[data-bulk-actions]')).toHaveCount(0);
      const unavailable = list(emptyId).locator('.admin-member-action-help');
      await unavailable.locator('summary').press('Enter');
      await expect(unavailable.getByText('Программа оценки не подключена. Обратитесь к суперадминистратору.')).toBeVisible();
    });

    await test.step('Отдельный импорт списка через штатный API', async () => {
      const disclosure = card(emptyId).locator('.admin-people-import');
      const csv = disclosure.getByLabel('Файл списка участников');
      await disclosure.locator('summary').press('Enter');
      await expect(csv).toBeVisible();
      const submit = disclosure.getByRole('button', { name: 'Импорт', exact: true });
      await submit.press('Enter');
      await expect(csv).toBeFocused();
      expect(requests).toHaveLength(1);
      await csv.setInputFiles({ name: 'participants.csv', mimeType: 'text/csv',
        buffer: Buffer.from('email,full_name,role_description\ncsv-adm-vis-03@example.test,Синтетический импорт,Специалист\n') });
      const imported = post(emptyId, 'members/import');
      await submit.press('Enter');
      expect((await imported).status()).toBe(200);
      await expect(disclosure.getByRole('status')).toContainText('Импортировано: 1');
      await expect(disclosure.locator('[data-csv-reselect]')).toHaveCount(0);
      await expect(list(emptyId).locator('.admin-organization-member')).toHaveCount(2);
    });

    await test.step('Серверный отказ без данных и переход к сведениям организации', async () => {
      await choose(id);
      const member = row(fixture.member_id);
      const help = member.locator('.admin-member-action-help');
      await expect(help).toContainText('Анкета для выбранной оценки не подтверждена');
      await expect(action('assign')).toHaveCount(0);
      await help.locator('summary').press('Enter');
      await help.getByRole('button', { name: 'Открыть данные организации' }).press('Enter');
      await expect(card(id).locator('[data-admin-view="organization-data"]')).toBeVisible();
      await card(id).getByRole('button', { name: 'Участники оценки' }).click();
      const invited = post(id, 'personal-invitations');
      await member.getByRole('button', { name: 'Пригласить', exact: true }).click();
      expect((await (await invited).json()).items[0]).toMatchObject({ reason_code: 'questionnaire_unconfirmed', outcome: 'failed' });
      await expect(member).toContainText('не подтверждены сведения организации');
      await member.getByRole('button', { name: 'Проверить сведения организации' }).click();
      await expect(card(id).locator('[data-admin-view="organization-data"]')).toBeVisible();
      const rejected = await page.request.post(base + '/users/admin/organizations/' + id + '/assessment-assignments', { data: {
        assignment_ref: fixture.ref, role_profile_version_id: fixture.role, user_ids: [fixture.member_id], operation_id: randomUUID(),
      } });
      expect(rejected.status()).toBe(409);
      expect(await rejected.json()).toMatchObject({ detail: 'ASSIGNMENT_QUESTIONNAIRE_NOT_CONFIRMED' });
    });

    await test.step('Фильтр и открытие обращения с восстановлением фокуса', async () => {
      JSON.parse(run(inputs, 'prepare-participant-appeal'));
      await page.reload();
      await choose(id);
      await card(id).getByRole('button', { name: 'Участники оценки' }).click();
      const appeal = row(fixture.appeal_member_id);
      const mark = appeal.getByRole('button', { name: 'Есть обращение' });
      const toggle = filter(id);
      await expect(toggle).toHaveText('С обращениями · 1');
      await row(fixture.member_id).getByRole('checkbox').check();
      for (const width of [1440, 390, 320]) {
        await page.setViewportSize({ width, height: 1000 });
        await toggle.press('Enter');
        await expect(toggle).toHaveText('Все участники');
        await expect(toggle).toHaveAttribute('aria-pressed', 'true');
        await expect(toggle).toBeFocused();
        await expect(list(id).getByRole('heading', { name: 'Участники с обращениями' })).toBeVisible();
        await expect(list(id).locator('.admin-organization-member')).toHaveCount(1);
        await expect(action('assign')).toHaveCount(0);
        await expect(action('invite').getByRole('button')).toBeDisabled();
        await mark.press('Enter');
        const dialog = page.getByRole('dialog', { name: 'Синтетический автор обращения' });
        await expect(dialog.getByRole('heading', { name: 'Обращения участника' })).toBeFocused();
        await expect(dialog).toContainText('Синтетическое обращение о должности');
        await page.keyboard.press('Escape');
        await expect(mark).toBeFocused();
        expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(width);
        await toggle.press('Enter');
        await expect(toggle).toHaveAttribute('aria-pressed', 'false');
        await expect(row(fixture.member_id).getByRole('checkbox')).not.toBeChecked();
      }
    });

    await test.step('Разные получатели двух пакетных команд, смена организации и серверная проверка роли', async () => {
      await choose(emptyId);
      await expect(list(emptyId).locator('[data-bulk-actions]')).toHaveCount(0);
      await choose(id);
      const scopedUrl = base + '/users/admin/organizations/' + id;
      const rejected = await page.request.post(scopedUrl + '/assessment-assignments', { data: {
        assignment_ref: fixture.ref, role_profile_version_id: fixture.unavailable_role, user_ids: [fixture.member_id], operation_id: randomUUID(),
      } });
      expect(rejected.status()).toBe(409);
      expect(await rejected.json()).toMatchObject({ detail: 'PROGRAM_ROLE_NOT_AVAILABLE' });
      const orgRead = await (await page.request.get(base + '/users/admin/organizations')).json();
      expect(orgRead.items.some((org) => org.id === fixture.foreign_organization_id)).toBe(false);
      const own = orgRead.items.find((org) => org.id === id);
      const emails = [fixture.member_id, fixture.appeal_member_id].map((id) => own.members.find((m) => m.user_id === id).email).sort();
      const invite = action('invite').getByRole('button', { name: 'Отправить приглашения' });
      const assign = action('assign').getByRole('button', { name: 'Назначить оценку' });
      await expect(invite).toBeDisabled();
      await expect(assign).toBeDisabled();
      const bulkSelect = list(id).getByRole('checkbox', { name: 'Выбрать доступных' });
      await bulkSelect.press('Space');
      await expect(bulkSelect).toBeChecked();
      await bulkSelect.press('Space');
      await expect(bulkSelect).not.toBeChecked();
      await expect(invite).toBeDisabled();
      for (const id of [fixture.member_id, fixture.appeal_member_id, fixture.registered_id]) {
        await row(id).getByRole('checkbox').press('Space');
      }
      await expect(action('invite')).toContainText('Подходят для действия: 2 из 3');
      await expect(action('assign')).toContainText('Подходят для действия: 2 из 3');
      const sent = post(id, 'personal-invitations');
      await invite.press('Enter');
      const sentResult = await sent;
      expect(sentResult.status()).toBe(200);
      expect(sentResult.request().postDataJSON()).toMatchObject({ emails, assignment_ref: fixture.ref });
      expect((await sentResult.json()).items.map((item) => item.outcome)).toEqual(['accepted', 'accepted']);
      await expect(list(id).locator('[data-people-batch-status]')).toContainText('Приняты сервисом: 2');
      await action('assign').getByLabel('Роль в оценке').selectOption(String(fixture.role));
      const assigned = post(id, 'assessment-assignments');
      await assign.press('Enter');
      const assignedResult = await assigned;
      expect(assignedResult.status()).toBe(200);
      expect(assignedResult.request().postDataJSON()).toMatchObject({ user_ids: [fixture.member_id, fixture.registered_id],
        assignment_ref: fixture.ref, role_profile_version_id: fixture.role });
      expect((await assignedResult.json()).items.map((item) => item.status)).toEqual(['assigned', 'assigned']);
      await expect(list(id).locator('[data-people-batch-status]')).toContainText('оценка назначена');
      await expect(row(fixture.registered_id).getByRole('checkbox')).toHaveCount(0);
      expect(errors).toEqual([]);
    });
    writeFileSync(info.outputPath('layout.json'), JSON.stringify(geometry, null, 2) + '\n');
  } finally {
    if (server && server.exitCode === null && server.signalCode === null) {
      const exited = once(server, 'exit');
      server.kill();
      await exited;
    }
    cli('destroy');
  }
});
