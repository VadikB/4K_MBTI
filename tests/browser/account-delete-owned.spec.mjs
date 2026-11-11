import { test, expect } from '@playwright/test';
import { spawn, spawnSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { randomUUID } from 'node:crypto';

test('F02 current people → HTTP → PostgreSQL, full graph, scope guards, receipt recovery', async ({ browser }) => {
  test.setTimeout(240000);
  if (!process.env.STAND_ADMIN_URL) throw new Error('Explicit owned localhost STAND_ADMIN_URL required');
  const python = process.env.BROWSER_PYTHON || path.join(process.cwd(), '.venv/bin/python');
  const directory = path.resolve(process.env.F02_BROWSER_EVIDENCE || '.test-stand/f02', randomUUID());
  fs.mkdirSync(directory, { recursive: true });
  const statePath = path.join(directory, 'state.json');
  const port = '18879', base = `http://127.0.0.1:${port}`;
  const run = (script, args) => {
    const result = spawnSync(python, [script, ...args], { encoding: 'utf8', timeout: 180000 });
    if (result.status !== 0) throw new Error(`${script} failed: ${result.stderr || result.stdout}`);
    return result.stdout.trim();
  };
  const cli = (action) => run('scripts/test_stand.py', [action, '--state', statePath, '--port', port]);
  const inputs = (action) => JSON.parse(run('tests/account_delete_browser_inputs.py', [action, '--state', statePath]));
  let server;
  const contexts = [], events = [], pageErrors = [];
  cli('create');
  try {
    cli('bootstrap'); cli('seed');
    const prepared = inputs('prepare'), initial = inputs('readback');
    const fd = fs.openSync(path.join(directory, 'server.log'), 'a');
    server = spawn(python, ['scripts/test_stand.py', 'serve', '--state', statePath, '--no-workers'], { stdio: ['ignore', fd, fd] });
    fs.closeSync(fd);
    await expect.poll(async () => { try { return (await fetch(base + '/health/ready')).status; } catch { return 0; } }, { timeout: 30000 }).toBe(200);
    const contextFor = async (label) => {
      const context = await browser.newContext(); contexts.push(context);
      await context.addCookies([{ name: prepared.cookie_name, value: prepared.sessions[label], url: base }]);
      return context;
    };
    const superContext = await contextFor('super'), adminContext = await contextFor('admin');
    const ordinaryContext = await contextFor('member'), page = await adminContext.newPage();
    page.setDefaultTimeout(15000);
    page.on('pageerror', (error) => pageErrors.push(error.message));
    await page.goto(base);
    await expect(page.locator('#admin-organizations-panel')).toBeVisible();
    const users = prepared.users;
    const purge = (user) => page.locator(`button[data-action="purge-account"][data-user-id="${user.id}"]`);
    const clickPurge = async (user) => {
      const button = purge(user);
      const menu = button.locator('xpath=ancestor::details');
      if (await menu.count() && (await menu.getAttribute('open')) === null) await menu.locator('summary').click();
      await button.click();
    };
    let confirmEmail = users.member.email;
    page.on('dialog', async (dialog) => dialog.type() === 'prompt' ? dialog.accept(confirmEmail) : dialog.accept());
    const status = page.locator('#admin-organizations-status');
    const list = await adminContext.request.get(base + '/users/admin/organizations');
    expect(list.status()).toBe(200);
    const listData = await list.json();
    expect(listData).not.toHaveProperty('excluded_accounts');
    expect(listData).not.toHaveProperty('detached_accounts');
    expect(await page.locator('.admin-excluded-accounts,.admin-detached-accounts').count()).toBe(0);
    expect(await page.getByRole('button', { name: /Исключить|Вернуть|Перенести/ }).count()).toBe(0);
    for (const [label, context, target, expected] of [
      ['ordinary', ordinaryContext, 'dual', 403], ['foreign', adminContext, 'foreign', 403],
      ['cross_scope_history', adminContext, 'scope', 403], ['self', adminContext, 'admin', 409],
      ['configured_superadmin', adminContext, 'super', 409], ['last_admin', superContext, 'last_admin', 409],
    ]) {
      const response = await context.request.get(base + `/users/admin/users/${users[target].id}/purge-preview`);
      expect(response.status(), label + ': ' + await response.text()).toBe(expected);
      const execute = await context.request.post(base + `/users/admin/users/${users[target].id}/purge`, { data: {
        confirmation_email: users[target].email, preview_fingerprint: '0'.repeat(64), operation_id: randomUUID(), acknowledge_irreversible: true,
      } });
      expect(execute.status(), label + ': ' + await execute.text()).toBe(expected);
      expect(inputs('readback')[target]).toEqual(initial[target]);
      events.push({ phase: label, preview: response.status(), execute: execute.status() });
    }
    const oldDelete = await adminContext.request.delete(base + `/users/admin/organizations/${prepared.organization_id}/members`, { params: { email: users.member.email } });
    expect(oldDelete.status()).toBe(410);
    expect(inputs('readback').member).toEqual(initial.member);
    // Known success must survive failure of cleanup after receipt (R01).
    await page.evaluate(() => {
      const original = Storage.prototype.setItem;
      Storage.prototype.setItem = function(key, value) {
        if (String(key).startsWith('agent4k.accountPurge.') && value === '[]') {
          window.f02CleanupFailures = (window.f02CleanupFailures || 0) + 1;
          throw new Error('synthetic cleanup failure');
        }
        return original.call(this, key, value);
      };
    });
    await clickPurge(users.member);
    await expect(status).toContainText('полностью удалены');
    await expect(status).not.toContainText('не отправлено');
    expect(await page.evaluate(() => window.f02CleanupFailures)).toBeGreaterThan(0);
    const deleted = inputs('readback');
    expect(Object.values(deleted.member.counts).every((count) => count === 0)).toBe(true);
    expect(deleted.member.receipts).toHaveLength(1);
    expect(deleted.member.receipts[0].actor_user_id).toBe(users.admin.id);
    expect(deleted.foreign).toEqual(initial.foreign);
    expect(deleted.organizations).toEqual(initial.organizations);
    events.push({ phase: 'member_delete_storage_failure', sql: deleted });
    await page.reload();
    const recovery = page.locator(`.admin-purge-recovery button[data-action="recover-purge-account"][data-user-id="${users.member.id}"]`);
    await expect(recovery).toBeVisible();
    await recovery.click();
    await expect(status).toContainText('полностью удалены');
    // Dual role, lost response after commit, same operation after reload.
    confirmEmail = users.dual.email;
    let command;
    const url = base + `/users/admin/users/${users.dual.id}/purge`;
    await page.route(url, async (route) => {
      command = route.request().postDataJSON();
      const response = await route.fetch();
      expect(response.status(), await response.text()).toBe(200);
      await route.abort('failed');
    }, { times: 1 });
    await clickPurge(users.dual);
    await expect(status).toContainText('Исход удаления пока неизвестен');
    expect(Object.values(inputs('readback').dual.counts).every((count) => count === 0)).toBe(true);
    await page.reload();
    let previewRequests = 0, recoveredCommand;
    page.on('request', (request) => {
      if (request.url() === url + '-preview') previewRequests++;
      if (request.url() === url && request.method() === 'POST') recoveredCommand = request.postDataJSON();
    });
    await page.locator(`.admin-purge-recovery button[data-action="recover-purge-account"][data-user-id="${users.dual.id}"]`).click();
    await expect(status).toContainText('полностью удалены');
    expect(recoveredCommand).toEqual(command);
    expect(previewRequests).toBe(0);
    const final = inputs('readback');
    expect(final.dual.receipts).toHaveLength(1);
    expect(final.dual.receipts[0].operation_id).toBe(command.operation_id);
    for (const label of ['foreign', 'scope', 'admin', 'last_admin', 'legacy', 'super']) expect(final[label]).toEqual(initial[label]);
    expect(final.organizations).toEqual(initial.organizations);
    events.push({ phase: 'dual_lost_commit_reply_recovered', same_command: true, previewRequests, sql: final });
    expect((await superContext.request.post(url, { data: command })).status()).toBe(409);
    const fresh = await contextFor('admin');
    const freshPayload = await (await fresh.request.get(base + '/users/admin/organizations')).json();
    expect(JSON.stringify(freshPayload)).not.toContain(users.member.email);
    expect(JSON.stringify(freshPayload)).not.toContain(users.dual.email);
    expect(freshPayload).not.toHaveProperty('excluded_accounts');
    expect(freshPayload).not.toHaveProperty('detached_accounts');
    expect(pageErrors).toEqual([]);
    await page.screenshot({ path: path.join(directory, 'f02-after-delete.png'), fullPage: true });
  } finally {
    fs.writeFileSync(path.join(directory, 'events.json'), JSON.stringify({ events, pageErrors }, null, 2) + '\n');
    await Promise.allSettled(contexts.map((context) => context.close()));
    if (server && server.exitCode === null) {
      const ended = new Promise((resolve) => server.once('exit', resolve)); server.kill('SIGTERM');
      await Promise.race([ended, new Promise((resolve) => setTimeout(resolve, 5000))]);
      if (server.exitCode === null) { server.kill('SIGKILL'); await ended; }
    }
    cli('destroy');
  }
});
