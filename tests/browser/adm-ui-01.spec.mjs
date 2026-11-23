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
  let releaseQuestionnaire;
  const questionnaireGate = new Promise((resolve) => { releaseQuestionnaire = resolve; });
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
    await page.route(base + '/users/admin/organizations/' + id + '/questionnaire', async (route) => {
      await questionnaireGate;
      await route.continue();
    }, { times: 1 });
    page.on('request', (request) => {
      if (new URL(request.url()).pathname.startsWith('/users/admin/')) requests.push(request);
    });
    await page.goto(base);
    const panel = page.locator('#admin-organizations-panel');
    await expect(panel).toBeVisible();
    const orgSelect = panel.locator('#admin-organization-select');
    await orgSelect.selectOption(String(id));
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
    const organizationLabel = await orgSelect.locator('option:checked').textContent();
    await expect(panel.locator('#admin-organizations-menu-role')).toHaveText(
      'Администратор ' + organizationLabel.split(' · ')[0],
    );
    await expect(panel.getByRole('button', { name: 'К сводке', exact: true })).toHaveCount(0);
    const logout = panel.getByRole('button', { name: 'Выйти', exact: true });
    await expect(logout).toBeVisible();
    await page.keyboard.press('Tab');
    await expect(logout).toBeFocused();
    await page.keyboard.press('Escape');
    await expect(summary).toBeFocused();
    await expect(row('assign').getByRole('button', { name: 'Пригласить', exact: true })).toBeVisible();
    const addForm = card.locator('form[data-action="add-member"]');
    for (const name of ['Email', 'ФИО', 'Должность']) await expect(addForm.getByLabel(name)).toBeEditable();
    await expect(card.getByLabel('Файл списка участников')).toBeVisible();

    const geometry = [];
    for (const width of [1440, 390, 320]) {
      await page.setViewportSize({ width, height: 1000 });
      await expect(panel).toHaveCSS('background-color', 'rgb(247, 247, 247)');
      await expect(panel.locator('#admin-organizations-title')).toHaveCSS('font-weight', '700');
      await expect(tabs.first()).toHaveCSS('font-size', width === 1440 ? '14px' : '13px');
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
      if (width === 1440) {
        releaseQuestionnaire();
        await expect(row('assign').getByRole('button', { name: 'Назначить оценку' })).toBeVisible();
        await expect(menu.getByRole('menuitem').last()).toBeFocused();
      } else {
        const popup = await menu.getByRole('menu').boundingBox();
        const trigger = await anchor.boundingBox();
        expect(popup.y).toBeGreaterThanOrEqual(trigger.y + trigger.height);
        expect(popup.x).toBeGreaterThanOrEqual(0);
        expect(popup.x + popup.width).toBeLessThanOrEqual(width);
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
    await expect(panel.locator('#admin-organizations-status')).toHaveText('Приглашение отозвано.');

    const old = fixture.invitations.unknown;
    expect(old.ref).not.toBe(fixture.ref);
    expect(await page.evaluate(() => Object.keys(window.localStorage).some((key) =>
      key.startsWith('agent4k.pendingInvitations.')))).toBe(false);
    const invitationRow = row('unknown');
    await expect(invitationRow.locator('.admin-organization-current-stage')).toHaveText('Оценка не назначена');
    await expect(invitationRow).toContainText('Отправка по другой оценке (' + old.ref + ')');
    const beforeLink = await invitationRow.locator('.admin-organization-member-invitation').first().innerText();
    const read = page.waitForResponse((response) => response.url().includes('/personal-invitations/operations/' + old.operation));
    const beforeReceipt = requests.length;
    await invitationRow.getByRole('button', { name: 'Проверить отправку' }).click();
    const receipt = await read;
    expect(receipt.status()).toBe(200);
    expect(receipt.request().method()).toBe('GET');
    const receiptUrl = new URL(receipt.url());
    expect(receiptUrl.pathname).toContain('/organizations/' + id + '/');
    expect(receiptUrl.searchParams.get('assignment_ref')).toBe(old.ref);
    expect(receiptUrl.searchParams.get('email')).toBe(old.email);
    const batch = (await receipt.json()).items;
    expect(batch).toHaveLength(2);
    expect(batch).toEqual(expect.arrayContaining([
      expect.objectContaining({ email: old.email, operation_id: old.operation, invitation_id: old.id, outcome: 'unknown' }),
      expect.objectContaining({ email: fixture.invitations.old_batch.email, operation_id: old.operation, outcome: 'accepted' }),
    ]));
    await expect(panel.locator('#admin-organizations-status')).toContainText('Отправка ещё не подтверждена');
    await expect(invitationRow.locator('.admin-organization-current-stage')).toHaveText('Оценка не назначена');
    await expect(invitationRow.locator('.admin-organization-member-invitation').first()).toHaveText(beforeLink);
    await expect(row('unverified_invitation')).toContainText('Не удалось подтвердить, к какой оценке относится отправка.');
    await expect(row('unverified_invitation').getByRole('button', { name: 'Проверить отправку' })).toHaveCount(0);
    await expect(row('unverified_invitation').getByRole('button', { name: 'Отозвать приглашение' }))
      .toHaveAttribute('data-invitation-id', String(fixture.invitations.unverified_invitation.id));
    expect(requests.slice(beforeReceipt).filter((request) => request.method() !== 'GET')).toEqual([]);

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
    await expect(row('running').locator('.admin-organization-current-stage')).toHaveText('Проверяем материалы ситуации');
    await row('running').getByRole('button', { name: 'Проверить состояние' }).click();
    await expect(dialog.locator('[data-card-check-feedback]')).toHaveText('Состояние обновлено.');
    await page.keyboard.press('Escape');
    await expect(row('running').getByRole('button', { name: 'Проверить состояние' })).toBeFocused();
    await expect(row('active').locator('.admin-organization-current-stage')).toHaveText('Оценка выполняется');
    await expect(row('failed').locator('.admin-organization-current-stage')).toHaveText('Не удалось завершить подготовку следующей ситуации');
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

    const organizations = await (await page.request.get(base + '/users/admin/organizations')).json();
    const selectedOrganization = organizations.items.find((item) => item.id === id);
    expect(selectedOrganization.assessment_program).toMatchObject({
      program_definition_id: fixture.program_id, pilot_plan_ref: { contract: 'm7_pilot_plan_admission/1' },
    });
    const people = selectedOrganization.members;
    for (const [key, generalProfile, label, start] of [
      ['profile_ready', false, 'Заполнены', 'Заблокирован'],
      ['profile_pending', true, 'Нет подтверждённых сведений', 'Нет подтверждённых сведений'],
    ]) {
      const member = people.find((item) => item.user_id === fixture.members[key]);
      const profile = fixture.profiles[key];
      expect(member.assessment_profile_ready).toBe(generalProfile);
      const stage = member.assessment_stages[fixture.ref];
      expect(stage.assignment_id).toBe(profile.assignment_id);
      expect(stage.profile_readiness).toEqual(profile.profile_id
        ? { personalized_profile_id: profile.profile_id, status: 'ready' } : null);
      await memberCard(key).click();
      await dialog.locator('.admin-member-history summary').click();
      await expect(dialog.locator('[data-card-profile]')).toHaveText(label);
      await expect(dialog.locator('[data-card-start]')).toHaveText(start);
      await page.keyboard.press('Escape');
      await expect(dialog).toBeHidden();
    }

    const openReports = () => card.getByRole('button', { name: 'Отчёты организации' }).click();
    const registry = page.locator('#admin-reports-panel');
    const registryOrganization = registry.locator('#admin-reports-organization');
    const registryProgram = registry.locator('#admin-reports-program');
    const selectedProgram = 'program-definition:' + fixture.program_id;
    const isRegistryResponse = (response) => new URL(response.url()).pathname === '/users/admin/m8-access/reports';
    const registryOpen = (name) => registry.locator('.admin-report-row').filter({ hasText: name })
      .getByRole('button', { name: 'Открыть', exact: true });
    const reportBack = page.locator('#report-back-button');
    const checkReport = async (trigger, publication) => {
      const reading = page.waitForResponse((response) => response.url().endsWith('/m8-access/reports/' + publication.report_id));
      await trigger.click();
      const report = await reading;
      expect(report.status()).toBe(200);
      expect(await report.json()).toMatchObject({
        id: publication.report_id, cycle_id: publication.cycle_id, results_revision_id: publication.results_revision_id,
        audience: 'customer', program_name: 'Имя программы в отчёте',
      });
      await expect(page.locator('#m8-report-state')).toHaveText('Результат готов');
    };
    const cases = [
      ['ready', 'Полный результат', 'Открыть отчёт', 'Полный результат'],
      ['limited', 'Ограниченный результат', 'Открыть отчёт', 'Частичный или ограниченный результат'],
      ['no_result', 'Результат без балла', 'Открыть пояснение', 'Недостаточно оснований для результата'],
      ['without_score', 'Наблюдения без балла', 'Открыть пояснение', 'Есть наблюдения без общего балла'],
    ];
    for (const [key, name, label, result] of cases) {
      const publication = fixture.reports[key];
      const entry = row(key).getByRole('button', { name: label });
      await expect(entry).toHaveAttribute('data-report-id', publication.report_id);
      await expect(row(key).locator('.admin-organization-member-stage')).toContainText(result);
      await checkReport(entry, publication);
      if (key === 'ready') await page.reload();
      await reportBack.click();
      await expect(orgSelect).toHaveValue(String(id));
      await expect(row(key)).toBeVisible();
      await openReports();
      await expect(registryOrganization).toHaveValue(String(id));
      await expect(registryProgram).toHaveValue(selectedProgram);
      await checkReport(registryOpen(name), publication);
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
    await tabs.nth(2).click();
    await expect(card.locator('.admin-organization-head')).toBeHidden();
    await expect(card.getByRole('button', { name: 'Отчёты организации', exact: true })).toHaveCount(1);
    await openReports();
    await expect(registryOrganization).toHaveValue(String(id));
    await expect(registryProgram).toHaveValue(selectedProgram);
    await registry.getByRole('button', { name: 'К управлению' }).click();
    await expect(tabs.nth(2)).toHaveAttribute('aria-pressed', 'true');
    await expect(card.locator('[data-admin-view="questionnaire"] [name="assignment_ref"]')).toHaveValue(fixture.ref);
    await tabs.nth(1).click();
    await expect(card.locator('.admin-organization-head')).toBeHidden();
    const listing = page.waitForResponse(isRegistryResponse);
    await openReports();
    const filtered = await listing;
    const requested = new URL(filtered.url()).searchParams;
    expect(requested.get('organization_id')).toBe(String(id));
    expect(requested.get('program_definition_id')).toBe(String(fixture.program_id));
    expect(requested.get('program')).toBe('');
    expect((await filtered.json()).items.map((item) => item.cycle_id).sort()).toEqual(
      ['ready', 'limited', 'no_result', 'without_score', 'unavailable'].map((key) => fixture.reports[key].cycle_id).sort(),
    );
    const peer = await context.newPage();
    try {
      await peer.goto(base + '/?screen=admin-organizations');
      const peerSelect = peer.locator('#admin-organization-select');
      await peerSelect.selectOption(String(fixture.peer_org));
      const peerCard = peer.locator('[data-organization-id="' + fixture.peer_org + '"]');
      await expect(peerCard.locator('[data-admin-view="organization-data"] [name="assignment_ref"]'))
        .toHaveValue(fixture.peer_ref);
      const peerReports = peerCard.getByRole('button', { name: 'Отчёты организации' });
      const peerListing = peer.waitForResponse(isRegistryResponse);
      await peerReports.click();
      const emptyPilot = await peerListing;
      expect(new URL(emptyPilot.url()).searchParams.get('program_definition_id')).toBe(String(fixture.peer_program_id));
      expect(await emptyPilot.json()).toMatchObject({ organization_id: fixture.peer_org, total: 0 });
      await expect(peer.locator('#admin-reports-organization')).toHaveValue(String(fixture.peer_org));
      await expect(peer.locator('#admin-reports-program')).toHaveValue('program-definition:' + fixture.peer_program_id);
      await page.reload();
      await expect(registryOrganization).toHaveValue(String(id));
      await expect(registryProgram).toHaveValue(selectedProgram);
      await expect(registry.locator('.admin-report-row')).toHaveCount(5);
      await checkReport(registryOpen('Полный результат'), fixture.reports.ready);

      await peer.getByRole('button', { name: 'К управлению' }).click();
      await expect(peerSelect).toHaveValue(String(fixture.peer_org));
      await peerReports.click();
      await expect(peer.locator('#admin-reports-organization')).toHaveValue(String(fixture.peer_org));
      await page.reload();
      await expect(page.locator('#m8-report-state')).toHaveText('Результат готов');
      await reportBack.click();
      await expect(registryOrganization).toHaveValue(String(id));
      await expect(registryProgram).toHaveValue(selectedProgram);
      await expect(registry.locator('.admin-report-row')).toHaveCount(5);
      await registryProgram.selectOption('');
      await expect(registry.locator('.admin-report-row')).toHaveCount(7);
      await expect(registryOpen('Отчёт прежней версии программы')).toBeVisible();
      await expect(registryOpen('Исторический отчёт без привязки')).toBeVisible();
      await registry.getByRole('button', { name: 'К управлению' }).click();
      await expect(orgSelect).toHaveValue(String(id));
      await expect(tabs.nth(1)).toHaveAttribute('aria-pressed', 'true');
      await expect(card.locator('[data-admin-view="organization-data"] [name="assignment_ref"]')).toHaveValue(fixture.ref);
    } finally {
      await peer.close();
    }

    await test.step('AC-4 ordinary program opens all organization reports on the first request', async () => {
      const superadmin = await browser.newContext();
      let connected;
      try {
        await superadmin.addCookies([{ name: fixture.cookie_name, value: fixture.super_session, url: base }]);
        const connection = await superadmin.request.put(base + '/users/admin/organizations/' + id + '/assessment-program', {
          data: { program_definition_id: fixture.ordinary_program_id, operation_id: 'cabinet-connect-ordinary' },
        });
        expect(connection.status()).toBe(200);
        connected = (await connection.json()).connection;
        expect(connected.program_definition_id).toBe(fixture.ordinary_program_id);
        expect(connected).not.toHaveProperty('pilot_plan_ref');
      } finally {
        await superadmin.close();
      }
      await page.reload();
      const readiness = card.locator('[data-admin-view="organization-data"] .admin-data-readiness');
      await readiness.locator('summary').press('Enter');
      await expect(readiness.locator('.admin-assessment-identity')).toBeVisible();
      await expect(readiness.locator('.admin-assessment-identity')).toContainText(connected.program_version);
      await tabs.nth(2).click();
      const firstListing = page.waitForResponse(isRegistryResponse);
      await openReports();
      const general = await firstListing;
      expect(general.status()).toBe(200);
      const params = new URL(general.url()).searchParams;
      expect(params.get('organization_id')).toBe(String(id));
      expect(params.get('program')).toBe('');
      expect(params.has('program_definition_id')).toBe(false);
      const publication = fixture.reports.legacy_report;
      expect((await general.json()).items).toEqual(expect.arrayContaining([
        expect.objectContaining({ cycle_id: publication.cycle_id, report_id: publication.report_id, status: 'ready' }),
      ]));
      await expect(registryProgram.locator('option:checked')).toHaveText('Все программы');
      await checkReport(registryOpen('Исторический отчёт без привязки'), publication);
      await page.reload();
      await expect(page.locator('#m8-report-state')).toHaveText('Результат готов');
      await reportBack.click();
      await expect(registryOrganization).toHaveValue(String(id));
      await expect(registryProgram.locator('option:checked')).toHaveText('Все программы');
      await registry.getByRole('button', { name: 'К управлению' }).click();
      await expect(orgSelect).toHaveValue(String(id));
      await expect(tabs.nth(2)).toHaveAttribute('aria-pressed', 'true');
      await expect(card.locator('[data-admin-view="questionnaire"] [name="assignment_ref"]')).toHaveValue(fixture.ref);
    });

    const foreign = await browser.newContext();
    try {
      await foreign.addCookies([{ name: fixture.cookie_name, value: fixture.foreign_session, url: base }]);
      expect((await foreign.request.get(base + '/users/admin/m8-access/reports/' + fixture.reports.ready.report_id)).status()).toBe(403);
      expect((await foreign.request.get(base + '/users/admin/m8-access/reports/' + fixture.reports.legacy_report.report_id)).status()).toBe(403);
    } finally {
      await foreign.close();
    }
    expect(errors).toEqual([]);
    await info.attach('viewports', { body: JSON.stringify(geometry), contentType: 'application/json' });
  } finally {
    releaseQuestionnaire();
    if (server?.exitCode === null) {
      const ended = once(server, 'exit');
      server.kill('SIGTERM');
      await ended;
    }
    cli('destroy');
  }
});
