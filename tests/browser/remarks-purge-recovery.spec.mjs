import { test, expect } from '@playwright/test';
import { spawn, spawnSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { randomUUID } from 'node:crypto';

test('F02 AC03/04 current people, real clicks, HTTP and owned PostgreSQL: failure, lost reply before/after commit, reload, same receipt', async ({ browser }) => {
  test.setTimeout(180000);
  if (!process.env.STAND_ADMIN_URL) throw new Error('Explicit owned localhost STAND_ADMIN_URL required');
  const python = process.env.BROWSER_PYTHON || path.join(process.cwd(), '.venv/bin/python');
  const directory = path.join(process.env.REMARKS_PURGE_EVIDENCE || '.test-stand/remarks-purge', randomUUID());
  fs.mkdirSync(directory, { recursive: true });
  const statePath = path.resolve(directory, 'state.json');
  const port = '18880', base = `http://127.0.0.1:${port}`;
  const cli = (action) => {
    const result = spawnSync(python, ['scripts/test_stand.py', action, '--state', statePath, '--port', port], { encoding: 'utf8', timeout: 180000 });
    fs.appendFileSync(path.join(directory, 'stand.log'), result.stdout + result.stderr);
    if (result.status !== 0) throw new Error('stand ' + action + ' failed; see stand.log');
  };
  const inputs = (action) => {
    const result = spawnSync(python, ['tests/remarks_purge_browser_inputs.py', action, '--state', statePath], { encoding: 'utf8', timeout: 60000 });
    if (result.status !== 0) throw new Error(result.stderr);
    return JSON.parse(result.stdout.trim().split('\n').at(-1));
  };
  let server, context, ordinaryContext;
  const events = [], pageErrors = [], posts = [];
  cli('create');
  try {
    cli('bootstrap');
    const prepared = inputs('prepare');
    const fd = fs.openSync(path.join(directory, 'server.log'), 'a');
    server = spawn(python, ['scripts/test_stand.py', 'serve', '--state', statePath, '--no-workers'], { stdio: ['ignore', fd, fd] });
    fs.closeSync(fd);
    await expect.poll(async () => { try { return (await fetch(base + '/health/ready')).status; } catch { return 0; } }, { timeout: 30000 }).toBe(200);
    context = await browser.newContext();
    await context.addCookies([{ name: prepared.cookie_name, value: prepared.super_session, url: base }]);
    const page = await context.newPage();
    page.on('pageerror', (error) => pageErrors.push(error.message));
    page.on('request', (request) => {
      if (/\/users\/admin\/users\/\d+\/purge$/.test(request.url()) && request.method() === 'POST') posts.push({ url: request.url(), command: request.postDataJSON() });
    });
    const openOrganizations = async () => {
      await page.goto(base);
      await page.getByRole('button', { name: 'Организации', exact: true }).click();
      await expect(page.locator('#admin-organizations-panel')).toBeVisible();
      await page.locator('#admin-organization-select').selectOption(String(prepared.organization_id));
    };
    await openOrganizations();
    const status = page.locator('#admin-organizations-panel [data-operation-status]:visible, #admin-organizations-status:visible').last();
    const before = prepared.users.before, after = prepared.users.after;
    const purge = (user) => page.locator(`button[data-action="purge-account"][data-user-id="${user.id}"]`);
    const clickPurge = async (user) => {
      const menu = purge(user).locator('xpath=ancestor::details');
      if (await menu.getAttribute('open') === null) await menu.locator('summary').click();
      await purge(user).click();
    };
    const recovery = (user) => page.locator(`.admin-purge-recovery button[data-action="recover-purge-account"][data-user-id="${user.id}"]`);
    let confirmEmail = before.email;
    page.on('dialog', async (dialog) => dialog.type() === 'prompt' ? dialog.accept(confirmEmail) : dialog.accept());

    // Actual permission denial and self-delete protection use the real server and PG.
    ordinaryContext = await browser.newContext();
    await ordinaryContext.addCookies([{ name: prepared.cookie_name, value: prepared.ordinary_session, url: base }]);
    expect((await ordinaryContext.request.get(base + `/users/admin/users/${before.id}/purge-preview`)).status()).toBe(403);
    const previewSelf = await page.request.get(base + `/users/admin/users/${prepared.users.super.id}/purge-preview`);
    expect(previewSelf.status()).toBe(409);
    expect((await previewSelf.json()).detail).toBe('CANNOT_PURGE_CURRENT_ACCOUNT');
    const selfDenied = await page.request.post(base + `/users/admin/users/${prepared.users.super.id}/purge`, { data: {
      confirmation_email: prepared.users.super.email, preview_fingerprint: '0'.repeat(64),
      operation_id: randomUUID(), acknowledge_irreversible: true,
    } });
    expect(selfDenied.status()).toBe(409);
    expect((await selfDenied.json()).detail).toBe('CANNOT_PURGE_CURRENT_ACCOUNT');
    events.push({ phase: 'real_permission_and_self_guards', preview403: true, selfPreview409: true, selfExecute409: true, sql: inputs('readback') });

    for (const fault of ['network', '403', '409', '503']) {
      const previewUrl = base + `/users/admin/users/${before.id}/purge-preview`;
      await page.route(previewUrl, async (route) => fault === 'network' ? route.abort('failed') : route.fulfill({
        status: Number(fault), contentType: 'application/json', body: JSON.stringify({ detail: fault === '409' ? 'PURGE_ATTRIBUTION_SCHEMA_UNSAFE' : 'Technical unsafe internal detail' }),
      }), { times: 1 });
      await clickPurge(before);
      await expect(status).toBeVisible();
      await expect(status).not.toContainText('Failed to fetch');
      await expect(status).not.toContainText('Technical unsafe');
      await expect(purge(before)).toBeEnabled();
      expect(inputs('readback').before.exists).toBe(true);
      events.push({ phase: 'preview_refusal_' + fault, message: await status.textContent() });
    }

    // Real execute denials pass through the production click path and restore confirmation actions.
    for (const fault of ['403', '409']) {
      const url = base + `/users/admin/users/${before.id}/purge`;
      await page.route(url, async (route) => {
        const command = route.request().postDataJSON();
        const response = fault === '403'
          ? await ordinaryContext.request.post(url, { data: command })
          : await route.fetch({ postData: JSON.stringify({ ...command, preview_fingerprint: '0'.repeat(64) }) });
        expect(response.status()).toBe(Number(fault));
        await route.fulfill({ response });
      }, { times: 1 });
      await clickPurge(before);
      await expect(status).toContainText(fault === '403' ? 'суперадминистратору' : 'Состав удаления изменился');
      await expect(purge(before)).toBeEnabled();
      expect(await recovery(before).count()).toBe(0);
      expect(inputs('readback').before).toEqual({ exists: true, receipts: [] });
      events.push({ phase: 'real_execute_' + fault, message: await status.textContent(), sql: inputs('readback') });
    }

    for (const user of [before, after]) {
      confirmEmail = user.email;
      const url = base + `/users/admin/users/${user.id}/purge`;
      let intercepted = false;
      await page.route(url, async (route) => {
        if (user === after) {
          const response = await route.fetch();
          expect(response.status()).toBe(200);
        }
        intercepted = true;
        await route.abort('failed');
      }, { times: 1 });
      await clickPurge(user);
      await expect.poll(() => intercepted).toBe(true);
      await expect(status).toContainText('Исход удаления пока неизвестен');
      const uncertain = inputs('readback');
      expect(uncertain[user === before ? 'before' : 'after'].exists).toBe(user === before);
      expect(uncertain[user === before ? 'before' : 'after'].receipts).toHaveLength(user === before ? 0 : 1);
      const firstCommand = posts.at(-1).command;
      events.push({ phase: user === before ? 'lost_before_commit' : 'lost_after_commit', command: firstCommand, sql: uncertain });
      await page.reload();
      await expect(recovery(user)).toBeVisible();
      // A new preview for a deleted target is forbidden during recovery.
      let previewRequests = 0;
      const previewListener = (request) => { if (request.url() === url + '-preview') previewRequests += 1; };
      page.on('request', previewListener);
      await recovery(user).click();
      await expect(status).toContainText('полностью удалены');
      expect(posts.at(-1).command).toEqual(firstCommand);
      expect(previewRequests).toBe(0);
      page.off('request', previewListener);
      const known = inputs('readback');
      expect(known[user === before ? 'before' : 'after'].exists).toBe(false);
      expect(known[user === before ? 'before' : 'after'].receipts).toHaveLength(1);
      expect(known[user === before ? 'before' : 'after'].receipts[0].operation_id).toBe(firstCommand.operation_id);
      expect(await recovery(user).count()).toBe(0);
      events.push({ phase: 'recovered_' + (user === before ? 'before' : 'after'), sql: known, same_operation: true, previewRequests });
    }
    expect(new Set(posts.map(({ command }) => command.operation_id)).size).toBe(4);
    expect(pageErrors).toEqual([]);
    await page.screenshot({ path: path.join(directory, 'purge-recovered.png'), fullPage: true });
  } finally {
    fs.writeFileSync(path.join(directory, 'events.json'), JSON.stringify({ events, pageErrors, posts }, null, 2) + '\n');
    await Promise.allSettled([context?.close(), ordinaryContext?.close()]);
    if (server && server.exitCode === null) {
      const ended = new Promise((resolve) => server.once('exit', resolve));
      server.kill('SIGTERM');
      await Promise.race([ended, new Promise((resolve) => setTimeout(resolve, 5000))]);
      if (server.exitCode === null) { server.kill('SIGKILL'); await ended; }
    }
    cli('destroy');
  }
});
