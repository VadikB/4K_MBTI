import { expect, test } from '@playwright/test';
import { spawn, spawnSync } from 'node:child_process';
import { randomUUID } from 'node:crypto';
import { once } from 'node:events';
import { closeSync, mkdirSync, openSync, readFileSync, writeFileSync } from 'node:fs';
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
  let collectionReads = 0;
  const errors = [];
  page.on('pageerror', (error) => errors.push(error.message));
  page.on('request', (request) => {
    if (request.method() === 'POST' && request.url().startsWith(base + '/users/admin/organizations/')) requests.push(request);
    if (request.method() === 'GET' && request.url() === base + '/users/admin/organizations') collectionReads += 1;
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

    await test.step('Выбор файла, скачивание, импорт шаблона и ошибка внутри блока', async () => {
      const disclosure = card(emptyId).locator('.admin-people-import');
      const summary = disclosure.locator('summary');
      const template = disclosure.getByRole('link', { name: 'Скачать шаблон' });
      const chooseFile = disclosure.getByRole('button', { name: 'Выбрать файл' });
      const submit = disclosure.getByRole('button', { name: 'Загрузить' });
      const fileName = disclosure.locator('[data-member-file-name]');
      const status = disclosure.locator('[data-member-import-status]');
      let importedCount = 0;
      const selectFile = async (name, content) => {
        const opened = page.waitForEvent('filechooser');
        await chooseFile.press('Enter');
        await (await opened).setFiles({ name, mimeType: 'text/csv', buffer: Buffer.from(content) });
        await expect(fileName).toHaveText(name);
        await expect(submit).toBeEnabled();
      };
      expect(requests).toHaveLength(1);
      for (const width of [1440, 390, 320]) {
        await page.setViewportSize({ width, height: 1000 });
        await expect(template).toBeHidden();
        await summary.press('Enter');
        await expect(submit).toBeDisabled();
        await page.keyboard.press('Tab');
        await expect(template).toBeFocused();
        const downloaded = page.waitForEvent('download');
        await page.keyboard.press('Enter');
        const header = readFileSync(await (await downloaded).path(), 'utf-8');
        expect(header.trim()).toBe('Email,ФИО,Должность');
        await page.keyboard.press('Tab');
        await expect(chooseFile).toBeFocused();

        await selectFile('spisok-uchastnikov-' + width + '-dlinnoye-imya.csv',
          header + 'csv-' + width + '-adm-vis-03@example.test,Синтетический импорт ' + width + ',Специалист\n');
        expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(width);
        if (process.env.ADM_VIS_R2_VISUAL === '1') {
          await disclosure.screenshot({ path: info.outputPath('import-' + width + '.png') });
        }
        await page.keyboard.press('Tab');
        await expect(submit).toBeFocused();
        const imported = post(emptyId, 'members/import');
        await page.keyboard.press('Enter');
        expect((await imported).status()).toBe(200);
        await expect(status).toHaveText('Импортировано: 1. Пропущено: 0.');
        await expect(status).toHaveAttribute('data-tone', 'success');
        await expect(submit).toBeDisabled();
        importedCount += 1;
        await expect(list(emptyId).locator('.admin-organization-member')).toHaveCount(1 + importedCount);

        await selectFile('stroka-s-oshibkoy.csv', header + 'bad-address,Синтетическая ошибка,Специалист\n');
        const failed = post(emptyId, 'members/import');
        await submit.press('Enter');
        expect((await failed).status()).toBe(200);
        await expect(status).toHaveAttribute('data-tone', 'error');
        await expect(status).toContainText('email не указан или некорректен');
        await expect(fileName).toHaveText('stroka-s-oshibkoy.csv');
        expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(width);
        // A completed import uses the real collection response. Re-enter the organization for a fresh form.
        await choose(id);
        await choose(emptyId);
      }

      await summary.press('Enter');
      await selectFile('legacy.csv', 'email,full_name,role_description,job_instructions\nlegacy-adm-vis-03@example.test,Старый формат,Специалист,Работа с данными\n');
      const legacy = post(emptyId, 'members/import');
      await submit.press('Enter');
      expect((await legacy).status()).toBe(200);
      await expect(status).toHaveText('Импортировано: 1. Пропущено: 0.');
      await expect(list(emptyId).getByRole('button', { name: 'Старый формат' })).toBeVisible();

      await selectFile('mixed.csv', 'Email,ФИО,Должность\nwrong,Неверная строка,Специалист\nmixed-adm-vis-03@example.test,Корректная строка,Инженер\n');
      const mixed = post(emptyId, 'members/import');
      await submit.press('Enter');
      expect((await mixed).status()).toBe(200);
      await expect(status).toContainText('Импортировано: 1. Пропущено: 1.');
      await expect(status).toContainText('Строка 2: email не указан или некорректен');
      await expect(list(emptyId).getByRole('button', { name: 'Корректная строка' })).toBeVisible();

      await selectFile('empty.csv', '');
      await submit.press('Enter');
      await expect(status).toHaveText('CSV-файл пуст. Заполните шаблон и выберите файл снова.');
      expect(requests.filter((request) => request.url().endsWith('/members/import'))).toHaveLength(8);
    });

    await test.step('Параллельные импорт и ручное добавление обновляют список', async () => {
      const collectionUrl = base + '/users/admin/organizations';
      const membersUrl = collectionUrl + '/' + emptyId + '/members';
      const disclosure = card(emptyId).locator('.admin-people-import');
      const status = disclosure.locator('[data-member-import-status]');
      for (const [index, delayedAction, holdResponse] of [
        [1, 'members/import', false], [2, 'members', false], [3, 'members/import', true],
      ]) {
        const csvName = 'Параллельный импорт ' + index;
        const manualName = 'Параллельное добавление ' + index;
        const csvEmail = 'concurrent-csv-' + index + '@example.test';
        const manualEmail = 'concurrent-manual-' + index + '@example.test';
        const rowByName = (name) => list(emptyId).getByRole('button', { name, exact: true });
        const submitImport = () => disclosure.getByRole('button', { name: 'Загрузить' }).click();
        const submitManual = () => add.getByRole('button', { name: 'Добавить', exact: true }).click();
        const importFirst = delayedAction === 'members/import';
        const delayedUrl = importFirst ? membersUrl + '/import' : membersUrl;
        const requestCount = requests.length;
        const collectionReadCount = collectionReads;
        const csv = 'Email,ФИО,Должность\n' + csvEmail + ',' + csvName + ',Специалист\n';
        const { promise: held, resolve: markHeld } = Promise.withResolvers();
        const { promise: released, resolve: release } = Promise.withResolvers();
        await page.route(delayedUrl, async (route) => {
          const response = holdResponse ? await route.fetch() : null;
          markHeld();
          await released;
          if (response) await route.fulfill({ response });
          else await route.continue();
        }, { times: 1 });

        try {
          await disclosure.locator('[name="csv"]').setInputFiles({ name: 'concurrent.csv', mimeType: 'text/csv',
            buffer: Buffer.from(csv + (importFirst ? '' : 'bad-address,Строка с ошибкой,Специалист\n')) });
          await add.getByLabel('Email').fill(manualEmail);
          await add.getByLabel('ФИО').fill(manualName);
          await add.getByLabel('Должность').fill('Аналитик');
          const delayed = post(emptyId, delayedAction);
          await (importFirst ? submitImport() : submitManual());
          await held;
          const immediate = post(emptyId, importFirst ? 'members' : 'members/import');
          await (importFirst ? submitManual() : submitImport());
          expect((await immediate).status()).toBe(200);
          await expect(rowByName(importFirst ? manualName : csvName)).toBeVisible();
          if (holdResponse) {
            // The older POST has committed but its collection snapshot predates the manual add.
            await page.evaluate(({ orgId, email }) => {
              const selector = '[data-organization-id="' + orgId + '"] .admin-people-list [data-email="' + email + '"]';
              window.manualRowDisappeared = false;
              window.rosterObserver = new MutationObserver(() => {
                if (!document.querySelector(selector)) window.manualRowDisappeared = true;
              });
              window.rosterObserver.observe(document.querySelector('#admin-organizations-list'), { childList: true, subtree: true });
            }, { orgId: emptyId, email: manualEmail });
          } else {
            await expect(rowByName(importFirst ? csvName : manualName)).toHaveCount(0);
          }
          release();
          const delayedResponse = await delayed;
          expect(delayedResponse.status()).toBe(200);
          if (holdResponse) {
            const receipt = await delayedResponse.json();
            expect(receipt.organizations.items.find((org) => org.id === emptyId).members.map((member) => member.email))
              .not.toContain(manualEmail);
          }
          const saved = await (await page.request.get(collectionUrl)).json();
          const emails = saved.items.find((org) => org.id === emptyId).members.map((member) => member.email);
          expect(emails).toEqual(expect.arrayContaining([csvEmail, manualEmail]));
          await expect(status).toHaveText(importFirst ? 'Импортировано: 1. Пропущено: 0.' :
            'Импортировано: 1. Пропущено: 1. Строка 3: email не указан или некорректен');
          await expect(rowByName(csvName)).toHaveCount(1);
          await expect(rowByName(manualName)).toHaveCount(1);
          await expect(picker).toHaveValue(String(emptyId));
          await expect(disclosure).toHaveAttribute('open', '');
          expect(collectionReads - collectionReadCount).toBe(1);
          expect(requests.slice(requestCount).map((request) => request.url()).sort())
            .toEqual([membersUrl, membersUrl + '/import']);
          if (holdResponse) {
            expect(await page.evaluate(() => {
              window.rosterObserver.disconnect();
              return window.manualRowDisappeared;
            })).toBe(false);
          }
        } finally {
          release();
        }
      }
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
      await member.locator('.admin-organization-member-menu summary').press('Enter');
      await member.getByRole('menuitem', { name: 'Проверить сведения организации' }).press('Enter');
      await expect(card(id).locator('[data-admin-view="organization-data"]')).toBeVisible();
      const rejected = await page.request.post(base + '/users/admin/organizations/' + id + '/assessment-assignments', { data: {
        assignment_ref: fixture.ref, role_profile_version_id: fixture.role, user_ids: [fixture.member_id], operation_id: randomUUID(),
      } });
      expect(rejected.status()).toBe(409);
      expect(await rejected.json()).toMatchObject({ detail: 'ASSIGNMENT_QUESTIONNAIRE_NOT_CONFIRMED' });
    });

    await test.step('Смешанные строки, меню и открытие обращения с восстановлением фокуса', async () => {
      JSON.parse(run(inputs, 'prepare-participant-appeal'));
      const organizationUrl = base + '/users/admin/organizations/' + id;
      const sentEmail = 'sent-adm-vis-03@example.test';
      const created = await page.request.post(organizationUrl + '/members', { data: {
        email: sentEmail, full_name: 'Синтетический получатель письма', role_description: 'Менеджер',
      } });
      expect(created.status()).toBe(200);
      const sentMember = (await created.json()).items.find((org) => org.id === id).members.find((m) => m.email === sentEmail);
      const sent = await page.request.post(organizationUrl + '/personal-invitations', { data: {
        emails: [sentEmail], assignment_ref: fixture.ref, operation_id: randomUUID(),
      } });
      expect((await sent.json()).items[0]).toMatchObject({ outcome: 'accepted' });
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
        for (const [userId, main, extras] of [
          [fixture.member_id, 'Пригласить', ['Назначить оценку']],
          [sentMember.user_id, 'Назначить оценку', ['Отправить письмо повторно', 'Отозвать приглашение']],
          [fixture.appeal_member_id, 'Пригласить', ['Отменить назначение оценки']],
          [fixture.registered_id, 'Назначить оценку', []],
        ]) {
          const actions = row(userId).locator('.admin-organization-member-actions');
          await expect(actions.locator(':scope > button')).toHaveText([main]);
          const menu = actions.locator('summary');
          await expect(menu).toHaveCount(extras.length ? 1 : 0);
          if (!extras.length) continue;
          await menu.press('Enter');
          const entries = actions.getByRole('menuitem');
          await expect(entries).toHaveText(extras);
          await expect(entries.first()).toBeFocused();
          if (extras.length > 1) {
            await page.keyboard.press('ArrowDown');
            await expect(entries.last()).toBeFocused();
          }
          if (userId === fixture.member_id) {
            await page.keyboard.press('Enter');
            const dialog = page.getByRole('dialog', { name: 'Назначить оценку' });
            await expect(dialog.getByLabel('Роль в оценке')).toBeFocused();
            await page.keyboard.press('Escape');
            await expect(dialog).toBeHidden();
          } else {
            await page.keyboard.press('Escape');
          }
          await expect(menu).toBeFocused();
          await expect(menu).toHaveAttribute('aria-expanded', 'false');
        }
        await toggle.press('Enter');
        await expect(toggle).toHaveText('Все участники');
        await expect(toggle).toHaveAttribute('aria-pressed', 'true');
        await expect(toggle).toBeFocused();
        await expect(list(id).getByRole('heading', { name: 'Участники с обращениями' })).toBeVisible();
        await expect(list(id).locator('.admin-organization-member')).toHaveCount(1);
        await expect(action('assign')).toHaveCount(0);
        await expect(action('invite').getByRole('button')).toBeDisabled();
        await expect(mark).toHaveCSS('background-color', 'rgba(0, 0, 0, 0)');
        await expect(mark).toHaveCSS('color', 'rgb(0, 125, 137)');
        await expect(mark).toHaveCSS('text-decoration-line', 'underline');
        await expect(mark).toHaveCSS('font-size', '13px');
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
