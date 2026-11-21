import { test, expect } from '@playwright/test';
import { spawn, spawnSync } from 'node:child_process';
import { once } from 'node:events';
import fs from 'node:fs';
import path from 'node:path';

test('ADM-UI-01 organization cabinet on owned PostgreSQL', async ({ page, context, browser }, info) => {
  test.setTimeout(120000);
  if (!process.env.STAND_ADMIN_URL) throw new Error('Explicit isolated STAND_ADMIN_URL required');
  const python = process.env.BROWSER_PYTHON || path.join(process.cwd(), '.venv/bin/python');
  const port = 18874;
  const base = 'http://127.0.0.1:' + port;
  const stand = info.outputPath('state.json');
  fs.mkdirSync(path.dirname(stand), { recursive: true });
  const command = (file, action, options = []) => {
    const run = spawnSync(python, [file, action, '--state', stand, ...options],
      { encoding: 'utf8', timeout: 45000 });
    if (run.status !== 0) throw new Error(action + ': ' + run.stderr);
    return run.stdout;
  };
  const cli = (action) => command('scripts/test_stand.py', action, ['--port', String(port)]);
  let server;
  cli('create');
  try {
    cli('bootstrap');
    cli('seed');
    const fixture = JSON.parse(command('tests/path_admin_browser_inputs.py', 'cabinet').trim().split('\n').at(-1));
    const id = fixture.organization_id;
    const log = fs.openSync(info.outputPath('server.log'), 'w');
    server = spawn(python, ['scripts/test_stand.py', 'serve', '--state', stand, '--no-workers'], { stdio: ['ignore', log, log] });
    fs.closeSync(log);
    await expect.poll(async () => {
      try { return (await fetch(base + '/health/ready')).status; } catch { return 0; }
    }, { timeout: 30000 }).toBe(200);
    await context.addCookies([{ name: fixture.cookie_name, value: fixture.session, url: base }]);
    await context.grantPermissions(['clipboard-read', 'clipboard-write']);
    const errors = [];
    page.on('pageerror', (error) => errors.push(error.message));
    const requests = [];
    page.on('request', (request) => {
      if (new URL(request.url()).pathname.startsWith('/users/admin/')) requests.push(request);
    });
    await page.goto(base);
    const panel = page.locator('#admin-organizations-panel');
    await expect(panel).toBeVisible();
    const orgSelect = panel.locator('#admin-organization-select');
    const card = panel.locator('[data-organization-id="' + id + '"]');
    const row = (key) => card.locator('[data-member-user-id="' + fixture.members[key] + '"]');
    const memberCard = (key) => row(key).locator('[data-action="open-member-card"]');
    const sent = row('sent');
    const menu = sent.locator('.admin-organization-member-menu');
    const anchor = menu.locator('summary');
    const tabs = card.locator('.admin-organization-steps button');
    await expect(tabs).toHaveText(['Участники оценки', 'Данные организации', 'Анкета']);
    await expect(card.locator('.admin-organization-steps + .admin-organization-head')).toContainText('Synthetic test program');
    const summary = panel.locator('.org-admin-account-menu summary');
    await summary.focus();
    await page.keyboard.press('Enter');
    await expect(panel.getByRole('button', { name: 'Выйти' })).toBeVisible();
    await page.keyboard.press('Escape');
    await expect(summary).toBeFocused();
    await expect(row('assign').getByRole('button', { name: 'Пригласить', exact: true })).toBeVisible();
    const addForm = card.locator('form[data-action="add-member"]');
    for (const name of ['Email', 'ФИО', 'Должность']) await expect(addForm.getByLabel(name)).toBeEditable();
    await expect(card.getByLabel('Файл списка участников')).toBeVisible();

    const geometry = [];
    for (const width of [1440, 390, 320]) {
      await page.setViewportSize({ width, height: 1000 });
      await expect.poll(async () => card.evaluate((node, viewport) => {
        const list = node.querySelector('.admin-people-list').getBoundingClientRect();
        const add = node.querySelector('.admin-people-add').getBoundingClientRect();
        if (!list.width || !add.width) return false;
        return viewport === 1440
          ? Math.abs(add.x - list.right - 20) < 1 && Math.abs(add.width - 254) < 1 && add.y === list.y
          : add.y >= list.bottom;
      }, width)).toBe(true);
      if (process.env.ADM_UI_01_VISUAL === '1') {
        await page.locator('.admin-organizations-hero').scrollIntoViewIfNeeded();
        await page.screenshot({ path: info.outputPath('cabinet-' + width + '.png') });
      }
      await anchor.focus();
      await page.keyboard.press('Enter');
      await expect(menu.getByRole('menuitem')).toHaveText(['Отправить письмо повторно', 'Отозвать приглашение']);
      await expect(menu.getByRole('menuitem').first()).toBeFocused();
      await page.keyboard.press('Tab');
      await expect(menu.getByRole('menuitem').last()).toBeFocused();
      expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(width);
      if (width !== 1440) {
        const popup = await menu.getByRole('menu').boundingBox();
        const owner = await sent.boundingBox();
        const identity = await memberCard('sent').boundingBox();
        expect(popup.y).toBeGreaterThanOrEqual(identity.y + identity.height);
        expect(popup.y + popup.height).toBeLessThanOrEqual(owner.y + owner.height);
      }
      await page.keyboard.press('Escape');
      await expect(anchor).toBeFocused();
      await expect(menu).not.toHaveAttribute('open');
      geometry.push({ width, columns: width === 1440 ? 2 : 1, scrollWidth: width });
    }
    await page.setViewportSize({ width: 1440, height: 1000 });
    await anchor.click();
    await card.getByRole('heading', { name: 'Участники', exact: true }).click();
    await expect(menu).not.toHaveAttribute('open');
    await expect(sent.locator('[data-action="purge-account"]')).toHaveCount(0);
    await memberCard('sent').click();
    const dialog = page.locator('dialog.org-admin-member-card');
    await expect(dialog.locator('.admin-member-history')).not.toHaveAttribute('open');
    const remove = dialog.getByRole('button', { name: 'Удалить человека' });
    await expect(remove).toBeVisible();
    const preview = page.waitForResponse((response) => response.url().endsWith('/users/' + fixture.members.sent + '/purge-preview'));
    const dismissed = new Promise((resolve, reject) => {
      page.once('dialog', (confirmation) => confirmation.dismiss().then(resolve, reject));
    });
    await remove.click();
    expect((await preview).status()).toBe(200);
    await dismissed;
    await expect(remove).toBeEnabled();
    expect(requests.some((request) => request.url().endsWith('/purge') && request.method() === 'POST')).toBe(false);
    await page.keyboard.press('Escape');
    await expect(dialog).toBeHidden();
    await expect(memberCard('sent')).toBeFocused();

    await anchor.click();
    await menu.getByRole('menuitem', { name: 'Отозвать приглашение' }).click();
    await expect(menu).not.toHaveAttribute('open');
    const revoked = page.waitForResponse((response) =>
      response.request().method() === 'DELETE' && response.url().endsWith('/personal-invitations/' + fixture.invitations.sent.id));
    await page.getByRole('dialog', { name: 'Отозвать приглашение?' })
      .getByRole('button', { name: 'Отозвать приглашение' }).click();
    expect((await revoked).status()).toBe(200);
    await expect(sent.getByRole('button', { name: 'Пригласить снова' })).toBeVisible();

    const old = fixture.invitations.unknown;
    const read = page.waitForResponse((response) => response.url().includes('/personal-invitations/operations/' + old.operation));
    await row('unknown').getByRole('button', { name: 'Проверить отправку' }).click();
    const receipt = await read;
    expect(receipt.status()).toBe(200);
    expect(receipt.request().method()).toBe('GET');
    const receiptUrl = new URL(receipt.url());
    expect(receiptUrl.pathname).toContain('/organizations/' + id + '/');
    expect(receiptUrl.searchParams.get('assignment_ref')).toBe(fixture.ref);
    expect(receiptUrl.searchParams.get('email')).toBe(old.email);
    expect((await receipt.json()).items[0].invitation_id).toBe(old.id);
    expect(requests.filter((request) => request.method() === 'POST' && request.url().endsWith('/personal-invitations'))).toEqual([]);

    const assign = row('assign').getByRole('button', { name: 'Назначить оценку' });
    await assign.click();
    const assignment = page.getByRole('dialog', { name: 'Назначить оценку' });
    await expect(assignment).toContainText('Участник для назначения');
    await expect(assignment).toContainText('Synthetic test program');
    await assignment.getByLabel('Роль в оценке').selectOption(String(fixture.role));
    const posted = page.waitForResponse((response) => response.request().method() === 'POST' &&
      response.url().endsWith('/organizations/' + id + '/assessment-assignments'));
    await assignment.getByRole('button', { name: 'Назначить оценку' }).click();
    const saved = await posted;
    expect(saved.status()).toBe(200);
    expect(saved.request().postDataJSON()).toMatchObject({
      user_ids: [fixture.members.assign], assignment_ref: fixture.ref, role_profile_version_id: fixture.role,
    });
    await expect(row('assign').locator('.admin-organization-current-stage')).toHaveText('Оценка назначена');
    await expect(panel.locator('#admin-organizations-status')).toContainText('Участник для назначения: оценка назначена');

    const before = requests.length;
    await expect(row('running').locator('.admin-organization-current-stage')).toHaveText('Идёт подготовка оценки');
    await row('running').getByRole('button', { name: 'Проверить состояние' }).click();
    await expect(panel.locator('#admin-organizations-status')).toContainText('Состояние обновлено');
    await expect(row('active').locator('.admin-organization-current-stage')).toHaveText('Оценка выполняется');
    await expect(row('failed').locator('.admin-organization-current-stage')).toHaveText('Не удалось подготовить следующую ситуацию');
    await memberCard('failed').click();
    await expect(dialog.locator('[data-card-description]')).toHaveText('Оценка приостановлена. Завершено 0 из 2 ситуаций.');
    await expect(dialog).toContainText('Последний подтверждённый этап · Проверяем материалы ситуации');
    await expect(dialog.locator('[data-card-case]')).toContainText(fixture.cases.failed);
    await dialog.getByRole('button', { name: 'Скопировать номер' }).click();
    expect(await page.evaluate(() => navigator.clipboard.readText())).toBe(fixture.cases.failed);
    await dialog.getByRole('button', { name: 'Проверить состояние' }).click();
    await expect(dialog.locator('[data-card-check-feedback]')).toHaveText('Состояние обновлено.');
    expect(requests.slice(before).filter((request) => request.method() !== 'GET')).toEqual([]);
    if (process.env.ADM_UI_01_VISUAL === '1') await page.screenshot({ path: info.outputPath('incident.png') });
    await page.keyboard.press('Escape');
    await expect(memberCard('failed')).toBeFocused();

    const openReports = () => card.getByRole('button', { name: 'Отчёты организации' }).click();
    const registry = page.locator('#admin-reports-panel');
    const reportBack = page.locator('#report-back-button');
    const checkReport = async (trigger, publication) => {
      const reading = page.waitForResponse((response) => response.url().endsWith('/m8-access/reports/' + publication.report_id));
      await trigger.click();
      const report = await reading;
      expect(report.status()).toBe(200);
      expect(await report.json()).toMatchObject({ id: publication.report_id, cycle_id: publication.cycle_id, audience: 'customer' });
      await expect(page.locator('#m8-report-state')).toHaveText('Результат готов');
    };
    const cases = [
      ['ready', 'Полный результат', 'Открыть отчёт'], ['limited', 'Ограниченный результат', 'Открыть отчёт'],
      ['no_result', 'Результат без балла', 'Открыть пояснение'],
    ];
    for (const [key, name, label] of cases) {
      const publication = fixture.reports[key];
      const entry = row(key).getByRole('button', { name: label });
      await expect(entry).toHaveAttribute('data-report-id', publication.report_id);
      await checkReport(entry, publication);
      if (key === 'ready') await page.reload();
      await reportBack.click();
      await expect(orgSelect).toHaveValue(String(id));
      await expect(row(key)).toBeVisible();
      await openReports();
      await expect(registry.locator('#admin-reports-organization')).toHaveValue(String(id));
      await expect(registry.locator('#admin-reports-program')).toHaveValue('Synthetic test program');
      await checkReport(registry.locator('.admin-report-row').filter({ hasText: name }).getByRole('button', { name: 'Открыть', exact: true }), publication);
      if (key === 'ready') await page.reload();
      await reportBack.click();
      if (key === 'no_result') {
        const hiddenPublication = registry.locator('.admin-report-row').filter({ hasText: 'Публикация недоступна' });
        await expect(hiddenPublication).toBeVisible();
        await expect(hiddenPublication.getByRole('button', { name: 'Открыть', exact: true })).toHaveCount(0);
        expect((await page.request.get(base + '/users/admin/m8-access/reports?organization_id=' + fixture.other_org)).status()).toBe(403);
      }
      await registry.getByRole('button', { name: 'К управлению' }).click();
      await expect(orgSelect).toHaveValue(String(id));
      await expect(card.locator('.admin-organization-head')).toContainText('Synthetic test program');
    }
    await expect(row('unavailable').locator('[data-action="open-member-report"]')).toHaveCount(0);
    await tabs.nth(1).click();
    await openReports();
    await registry.getByRole('button', { name: 'К управлению' }).click();
    await expect(tabs.nth(1)).toHaveAttribute('aria-pressed', 'true');
    const foreign = await browser.newContext();
    try {
      await foreign.addCookies([{ name: fixture.cookie_name, value: fixture.foreign_session, url: base }]);
      expect((await foreign.request.get(base + '/users/admin/m8-access/reports/' + fixture.reports.ready.report_id)).status()).toBe(403);
    } finally {
      await foreign.close();
    }
    expect(errors).toEqual([]);
    await info.attach('viewports', { body: JSON.stringify(geometry), contentType: 'application/json' });
  } finally {
    if (server?.exitCode === null) {
      const ended = once(server, 'exit');
      server.kill('SIGTERM');
      await ended;
    }
    cli('destroy');
  }
});
