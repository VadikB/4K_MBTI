import { test, expect } from '@playwright/test';
import { spawn, spawnSync } from 'node:child_process';
import { once } from 'node:events';
import { mkdirSync, openSync, closeSync } from 'node:fs';
import { createServer } from 'node:net';
import path from 'node:path';

async function signIn(page, base, account) {
  await page.goto(base);
  await page.locator('#email-input').fill(account.email);
  await page.locator('#request-magic-link-button').click();
  await page.locator('#magic-token-input').fill(account.password);
  const loggedIn = page.waitForResponse(response =>
    response.url() === base + '/users/auth/email/password-login' && response.request().method() === 'POST');
  await page.locator('#verify-magic-link-button').click();
  expect((await loggedIn).status()).toBe(200);
}

test('ADM-UI-03 participant reads a reply after signing in again before completing acquaintance', async ({ browser }, info) => {
  test.setTimeout(120000);
  if (!process.env.STAND_ADMIN_URL) throw new Error('Explicit isolated STAND_ADMIN_URL required');
  const reservation = createServer();
  await new Promise((resolve, reject) => {
    reservation.once('error', reject);
    reservation.listen(0, '127.0.0.1', resolve);
  });
  const port = reservation.address().port;
  await new Promise(resolve => reservation.close(resolve));
  const base = 'http://127.0.0.1:' + port;
  const python = process.env.BROWSER_PYTHON || path.join(process.cwd(), '.venv/bin/python');
  const stand = info.outputPath('state.json');
  mkdirSync(path.dirname(stand), { recursive: true });
  const run = (file, action, args = []) => {
    const result = spawnSync(python, [file, action, '--state', stand, ...args], { encoding: 'utf8', timeout: 45000 });
    if (result.status !== 0) throw new Error(action + ': ' + (result.error || result.stderr));
    return result.stdout.trim().split('\n').at(-1);
  };
  const cli = (action) => run('scripts/test_stand.py', action, ['--port', String(port)]);
  const contexts = [];
  const newSession = async () => {
    const context = await browser.newContext();
    contexts.push(context);
    return context.newPage();
  };
  let server;
  cli('create');
  try {
    cli('bootstrap');
    cli('seed');
    const fixture = JSON.parse(run('tests/path_admin_browser_inputs.py', 'appeals-reentry'));
    const log = openSync(info.outputPath('server.log'), 'w');
    server = spawn(python, ['scripts/test_stand.py', 'serve', '--state', stand, '--no-workers'], { stdio: ['ignore', log, log] });
    closeSync(log);
    await expect.poll(async () => {
      try { return (await fetch(base + '/health/ready')).status; } catch { return 0; }
    }, { timeout: 30000 }).toBe(200);

    const participant = await newSession();
    const step = 'Проверьте ваши сведения';
    const issueText = 'Уточните синтетические сведения о моей должности.';
    const replyText = 'Проверили сведения. Спасибо за уточнение.';
    const issueUrl = base + '/users/' + fixture.member.id + '/acquaintance/issues';
    const journeyUrl = base + '/users/' + fixture.member.id + '/journey-state';
    await signIn(participant, base, fixture.member);
    await participant.getByRole('button', { name: 'Начать знакомство' }).click();
    await expect(participant.getByRole('heading', { name: step })).toBeVisible();
    await participant.getByRole('button', { name: 'Сообщить о неточности' }).click();
    const issue = participant.getByRole('dialog', { name: 'Сообщить о неточности' });
    await issue.getByLabel('Какие сведения нужно проверить?').selectOption('Должность');
    await issue.getByLabel('Что нужно уточнить?').fill(issueText);
    const reported = participant.waitForResponse(response =>
      response.url() === issueUrl && response.request().method() === 'POST');
    await issue.getByRole('button', { name: 'Отправить', exact: true }).click();
    const receipt = await reported;
    expect(receipt.status()).toBe(201);
    expect((await receipt.json()).assignment_id).toBe(fixture.assignment_id);
    await expect(participant.getByText('Сообщение сохранено в вашей организации')).toBeVisible();
    await expect.poll(async () => (await (await participant.request.get(journeyUrl)).json()).onboarding.current_step).toBe(1);
    const firstSession = (await participant.context().cookies()).find(cookie => cookie.name === 'agent4k_session_token');
    await participant.context().close();

    const admin = await newSession();
    await signIn(admin, base, fixture.admin);
    const organization = admin.locator('[data-organization-id="' + fixture.organization_id + '"]');
    const row = organization.locator('[data-member-user-id="' + fixture.member.id + '"]');
    await row.getByRole('button', { name: 'Есть обращение' }).click();
    const memberCard = admin.getByRole('dialog', { name: fixture.member.name });
    await expect(memberCard).toContainText(issueText);
    await memberCard.getByRole('button', { name: 'Взять в работу' }).click();
    await memberCard.getByLabel('Ответ участнику').fill(replyText);
    await memberCard.getByRole('button', { name: 'Отправить ответ' }).click();
    await expect(memberCard.getByRole('heading', { name: 'Ответ отправлен' })).toBeVisible();
    const savedAt = await memberCard.locator('.appeal-reply-attribution time').getAttribute('datetime');
    expect(savedAt).toBeTruthy();

    const returned = await newSession();
    await returned.setViewportSize({ width: 390, height: 844 });
    await signIn(returned, base, fixture.member);
    await expect(returned.getByRole('heading', { name: step })).toBeVisible();
    const newCookie = (await returned.context().cookies()).find(cookie => cookie.name === 'agent4k_session_token');
    expect(Boolean(firstSession && newCookie && firstSession.value !== newCookie.value)).toBe(true);
    const readJourney = async () => (await returned.request.get(journeyUrl)).json();
    const before = await readJourney();
    expect(before).toMatchObject({
      next_action: 'show_onboarding', can_open_dashboard: false,
      onboarding: { status: 'in_progress', current_step: 1 },
      assessment: { status: 'not_started', cycle_id: null },
      acquaintance: { mandatory_complete: false, assessment_name: null, late_readiness: { personalized_profile_id: null } },
    });
    const mutations = [];
    returned.on('request', request => {
      if (new URL(request.url()).pathname.startsWith('/users/') && request.method() !== 'GET') mutations.push(request.method());
    });
    const link = returned.locator('#onboarding-panel').getByRole('button', { name: 'Ответы на обращения' });
    const replies = returned.getByRole('dialog', { name: 'Ответы на обращения' });
    for (const width of [390, 320]) {
      await returned.setViewportSize({ width, height: 844 });
      const loaded = returned.waitForResponse(response => response.url() === issueUrl && response.request().method() === 'GET');
      await link.focus();
      await returned.keyboard.press('Enter');
      const response = await loaded;
      expect(response.status()).toBe(200);
      const { items } = await response.json();
      expect(items).toEqual([expect.objectContaining({
        assessment_display_name: fixture.assessment_name, assignment_id: fixture.assignment_id,
        reply_message: replyText, reply_author_display_name: fixture.admin.name, replied_at: savedAt,
      })]);
      await expect(replies.getByRole('heading', { name: 'Ответ по вашему обращению' })).toBeVisible();
      await expect(replies.getByText(fixture.assessment_name, { exact: true })).toBeVisible();
      await expect(replies.getByText(replyText, { exact: true })).toBeVisible();
      await expect(replies.locator('.appeal-reply-attribution')).toContainText(fixture.admin.name);
      await expect(replies.locator('time')).toHaveAttribute('datetime', savedAt);
      await expect(replies.locator('time')).not.toBeEmpty();
      expect(await replies.evaluate(dialog => dialog.scrollWidth <= dialog.clientWidth + 1 &&
        document.documentElement.scrollWidth === innerWidth)).toBe(true);
      if (width === 390) await replies.getByRole('button', { name: 'Вернуться к знакомству' }).click();
      else await returned.keyboard.press('Escape');
      await expect(replies).toBeHidden();
      await expect(link).toBeFocused();
      await expect(returned.getByRole('heading', { name: step })).toBeVisible();
    }
    await expect(returned.locator('#dashboard-panel')).toBeHidden();
    expect(await readJourney()).toMatchObject({
      next_action: before.next_action, can_open_dashboard: false, onboarding: before.onboarding,
      assessment: before.assessment,
    });
    expect(mutations).toEqual([]);
  } finally {
    await Promise.allSettled(contexts.map(context => context.close()));
    if (server && server.exitCode === null && server.signalCode === null) {
      const exited = once(server, 'exit');
      server.kill('SIGTERM');
      await exited;
    }
    cli('destroy');
  }
});
