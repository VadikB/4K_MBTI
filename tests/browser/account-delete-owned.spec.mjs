import { test, expect } from '@playwright/test';
import { spawn, spawnSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { randomUUID } from 'node:crypto';

test('ACCOUNT-DELETE-FIX-01: excluded member is discoverable and separate purge is guarded', async ({ browser }) => {
  test.setTimeout(180000);
  if (!process.env.STAND_ADMIN_URL) throw new Error('Explicit isolated STAND_ADMIN_URL required');
  const python = process.env.BROWSER_PYTHON || path.join(process.cwd(), '.venv/bin/python');
  const dir = path.join('.test-stand/account-delete', randomUUID());
  fs.mkdirSync(dir, { recursive: true });
  const statePath = path.resolve(dir, 'state.json');
  const port = '18879', base = `http://127.0.0.1:${port}`;
  const run = (script, args) => {
    const result = spawnSync(python, [script, ...args], { encoding: 'utf8', timeout: 180000 });
    if (result.status !== 0) throw new Error(`${script} failed: ${result.stderr || result.stdout}`);
    return result.stdout.trim();
  };
  const cli = (action) => run('scripts/test_stand.py', [action, '--state', statePath, '--port', port]);
  const inputs = (action, email = '') => JSON.parse(run('tests/account_delete_browser_inputs.py',
    [action, '--state', statePath, '--email', email]));
  let server, superContext, adminContext;
  cli('create');
  try {
    cli('bootstrap');
    cli('seed');
    const prepared = inputs('prepare');
    const fd = fs.openSync(path.join(dir, 'server.log'), 'a');
    server = spawn(python, ['scripts/test_stand.py', 'serve', '--state', statePath], { stdio: ['ignore', fd, fd] });
    fs.closeSync(fd);
    await expect.poll(async () => { try { return (await fetch(`${base}/health/ready`)).status; } catch { return 0; } },
      { timeout: 30000 }).toBe(200);
    superContext = await browser.newContext();
    await superContext.addCookies([{ name: prepared.cookie_name, value: prepared.session, url: base }]);
    const page = await superContext.newPage();
    await page.goto(base);
    await page.getByRole('button', { name: 'Организации', exact: true }).click();
    await expect(page.locator('#admin-organizations-panel')).toBeVisible();
    const org = prepared.organization_id;
    const list = async () => {
      const response = await page.request.get(`${base}/users/admin/organizations`);
      expect(response.status()).toBe(200);
      return response.json();
    };
    const member = 'account-delete-member@example.test';
    const admin = 'account-delete-admin@example.test';
    const foreign = 'account-delete-foreign@example.test';
    const detached = 'account-delete-detached@example.test';
    const addMember = async (organizationId, email) => {
      const response = await page.request.post(`${base}/users/admin/organizations/${organizationId}/members`, {
        data: { email, full_name: 'Synthetic account', role_description: 'Synthetic position' },
      });
      expect(response.status(), await response.text()).toBe(200);
    };
    const removeMember = async (organizationId, email) => {
      const response = await page.request.delete(`${base}/users/admin/organizations/${organizationId}/members`, {
        params: { email },
      });
      expect(response.status(), await response.text()).toBe(200);
    };
    await addMember(org, member);
    const saved = inputs('session', member);
    const before = inputs('readback', member);
    await removeMember(org, member);
    const excluded = inputs('readback', member);
    expect(excluded).toMatchObject({ user_id: saved.user_id, sessions: before.sessions,
      invitations: before.invitations, memberships: [{ role: 'member', is_participant: false }] });
    expect((await list()).excluded_accounts.map((item) => item.user_id)).toContain(saved.user_id);
    await page.reload();
    const excludedSection = page.locator('.admin-excluded-accounts');
    await expect(excludedSection).toContainText(member);
    await expect(excludedSection).toContainText('Синтетическая организация E10.2');
    await expect(excludedSection.getByRole('button', { name: 'Удалить полностью' })).toBeVisible();

    await addMember(org, member);
    expect(inputs('readback', member)).toMatchObject({ user_id: saved.user_id,
      sessions: before.sessions, invitations: before.invitations,
      memberships: [{ role: 'member', is_participant: true }] });
    expect((await list()).excluded_accounts.map((item) => item.user_id)).not.toContain(saved.user_id);
    await removeMember(org, member);

    const addAdmin = await page.request.post(`${base}/users/admin/organizations/${org}/admins`, {
      data: { email: admin, full_name: 'Synthetic excluded admin' },
    });
    expect(addAdmin.status(), await addAdmin.text()).toBe(200);
    await removeMember(org, admin);
    const adminState = inputs('readback', admin);
    expect(adminState.memberships).toMatchObject([{ role: 'admin', is_participant: false }]);
    const adminList = await list();
    expect(adminList.items.find((item) => item.id === org).admins.map((item) => item.email)).toContain(admin);
    expect(adminList.excluded_accounts.map((item) => item.email)).not.toContain(admin);

    const created = await page.request.post(`${base}/users/admin/organizations`, {
      data: { code: 'account_delete_other', name: 'Synthetic other organization' },
    });
    expect(created.status(), await created.text()).toBe(200);
    const otherOrg = (await created.json()).items.find((item) => item.code === 'account_delete_other').id;
    await addMember(otherOrg, foreign);
    await addMember(org, detached);
    const detachedId = inputs('detach', detached).user_id;
    const candidates = await list();
    expect(candidates.detached_accounts.map((item) => item.user_id)).toContain(detachedId);
    expect(candidates.detached_accounts.map((item) => item.email)).not.toContain(foreign);
    expect(candidates.excluded_accounts.map((item) => item.email)).not.toContain(foreign);

    const scoped = inputs('session', admin);
    adminContext = await browser.newContext();
    await adminContext.addCookies([{ name: prepared.cookie_name, value: scoped.session, url: base }]);
    const scopedRequest = await adminContext.request.get(`${base}/users/admin/organizations`);
    expect(scopedRequest.status()).toBe(200);
    expect((await scopedRequest.json()).excluded_accounts).toEqual([]);
    const denied = await adminContext.request.post(`${base}/users/admin/users/${saved.user_id}/purge`, {
      data: { confirmation_email: member, preview_fingerprint: '0'.repeat(64),
        operation_id: randomUUID(), acknowledge_irreversible: true },
    });
    expect(denied.status()).toBe(403);

    const previewResponse = await page.request.get(`${base}/users/admin/users/${saved.user_id}/purge-preview`);
    expect(previewResponse.status(), await previewResponse.text()).toBe(200);
    const preview = await previewResponse.json();
    const wrongEmail = await page.request.post(`${base}/users/admin/users/${saved.user_id}/purge`, {
      data: { confirmation_email: 'wrong@example.test', preview_fingerprint: preview.fingerprint,
        operation_id: randomUUID(), acknowledge_irreversible: true },
    });
    expect(wrongEmail.status()).toBe(409);
    const stale = await page.request.post(`${base}/users/admin/users/${saved.user_id}/purge`, {
      data: { confirmation_email: member, preview_fingerprint: '0'.repeat(64),
        operation_id: randomUUID(), acknowledge_irreversible: true },
    });
    expect(stale.status()).toBe(409);
    expect(inputs('readback', member).user_id).toBe(saved.user_id);

    await page.reload();
    let purgeRequest;
    page.on('request', (request) => {
      if (request.method() === 'POST' && request.url().endsWith(`/users/admin/users/${saved.user_id}/purge`)) {
        purgeRequest = request.postDataJSON();
      }
    });
    page.on('dialog', async (dialog) => {
      if (dialog.type() === 'prompt') await dialog.accept(member);
      else await dialog.accept();
    });
    await page.locator('.admin-excluded-accounts').getByRole('button', { name: 'Удалить полностью' }).click();
    await expect.poll(() => inputs('readback', member).user_id).toBeNull();
    expect(purgeRequest).toMatchObject({ confirmation_email: member, acknowledge_irreversible: true });
    const replay = await page.request.post(`${base}/users/admin/users/${saved.user_id}/purge`, { data: purgeRequest });
    expect(replay.status()).toBe(200);
    expect((await replay.json()).idempotent).toBe(true);
    expect(inputs('readback', foreign).user_id).toBeTruthy();
    expect(inputs('readback', admin).memberships[0].role).toBe('admin');
    expect(inputs('readback', detached).user_id).toBe(detachedId);
  } finally {
    await adminContext?.close();
    await superContext?.close();
    if (server && server.exitCode === null) {
      const ended = new Promise((resolve) => server.once('exit', resolve));
      server.kill('SIGTERM');
      await Promise.race([ended, new Promise((resolve) => setTimeout(resolve, 5000))]);
      if (server.exitCode === null) { server.kill('SIGKILL'); await ended; }
    }
    cli('destroy');
  }
});
