import { test, expect } from '@playwright/test';
import { spawn, spawnSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { randomUUID } from 'node:crypto';
import { capturePathViewports } from './fixtures/path-viewports.mjs';

test('AC09 actual HTTP+PostgreSQL: double click, committed lost response, reload and repeat', async ({ browser }) => {
  test.setTimeout(150000);
  if (!process.env.STAND_ADMIN_URL) throw new Error('Explicit isolated STAND_ADMIN_URL required');
  const python = process.env.BROWSER_PYTHON || path.join(process.cwd(), '.venv/bin/python');
  const dir = path.join(process.env.PATH_ADMIN_BROWSER_EVIDENCE || '.test-stand/path-admin-contract', randomUUID());
  fs.mkdirSync(dir, { recursive: true });
  const statePath = path.resolve(dir, 'state.json'), base = 'http://127.0.0.1:18872';
  const cli = (action) => {
    const result = spawnSync(python, ['scripts/test_stand.py', action, '--state', statePath, '--port', '18872'], { encoding: 'utf8', timeout: 180000 });
    fs.appendFileSync(path.join(dir, 'stand.log'), result.stdout + result.stderr);
    if (result.status !== 0) throw new Error('stand ' + action + ' failed; see stand.log');
  };
  const inputs = (action) => {
    const result = spawnSync(python, ['tests/path_admin_browser_inputs.py', action, '--state', statePath], { encoding: 'utf8', timeout: 60000 });
    if (result.status !== 0) throw new Error(result.stderr);
    return JSON.parse(result.stdout.trim().split('\n').at(-1));
  };
  let server, context, superContext;
  const events = [];
  cli('create');
  try {
    cli('bootstrap');
    cli('seed');
    const prepared = inputs('prepare');
    const fd = fs.openSync(path.join(dir, 'server.log'), 'a');
    server = spawn(python, ['scripts/test_stand.py', 'serve', '--state', statePath], { stdio: ['ignore', fd, fd] });
    fs.closeSync(fd);
    await expect.poll(async () => { try { return (await fetch(base + '/health/ready')).status; } catch { return 0; } }, { timeout: 30000 }).toBe(200);
    superContext = await browser.newContext();
    await superContext.addCookies([{ name: prepared.cookie_name, value: prepared.super_session, url: base }]);
    const superPage = await superContext.newPage();
    await superPage.goto(base);
    await superPage.getByRole('button', { name: 'Организации', exact: true }).click();
    await expect(superPage.locator('#admin-organizations-panel')).toBeVisible();
    await superPage.locator('#admin-organization-select').selectOption(String(prepared.organization_id));
    const superCard = superPage.locator(`[data-organization-id="${prepared.organization_id}"]`);
    await capturePathViewports(superPage, dir, 'superadmin-program', [
      { name: 'program', locator: superCard.locator('select[name="program_definition_id"]') },
      { name: 'connect', locator: superCard.locator('form[data-action="connect-assessment-program"]').getByRole('button', { name: 'Подключить' }) },
    ]);
    await superContext.close();
    context = await browser.newContext();
    await context.addCookies([{ name: prepared.cookie_name, value: prepared.session, url: base }]);
    const page = await context.newPage();
    const url = base + `/users/admin/organizations/${prepared.organization_id}/assessment-assignments`;
    let requests = 0;
    page.on('request', (request) => { if (request.url() === url && request.method() === 'POST') requests += 1; });
    await page.goto(base);
    await expect(page.locator('#admin-organizations-panel')).toBeVisible();
    const card = page.locator(`[data-organization-id="${prepared.organization_id}"]`);
    const people = card.getByRole('button', { name: 'Организация и участники', exact: true });
    const emails = Object.values(prepared.member_emails);
    const select = async (email) => {
      await people.click();
      for (const checkbox of await card.locator('input[name="invitation_email"]').all()) await checkbox.uncheck();
      await card.locator(`input[name="invitation_email"][value="${email}"]`).check();
    };
    const assign = card.getByRole('button', { name: 'Назначить оценку', exact: true });
    await select(emails[0]);
    const response = page.waitForResponse((r) => r.url() === url && r.request().method() === 'POST');
    await assign.dblclick();
    expect((await response).status()).toBe(200);
    await expect(card.locator('[data-operation-status]').first()).toContainText('Назначена: 1');
    const afterDouble = inputs('readback');
    expect(afterDouble.assignments).toHaveLength(1);
    expect(afterDouble.bindings).toHaveLength(1);
    expect(afterDouble.cycles).toBe(0);
    events.push({ phase: 'double_click', actual_post_requests: requests, sql: afterDouble });
    expect(requests).toBe(1); // Actual UI in-flight guard, in addition to server concurrency tests.

    await select(emails[1]);
    let committed;
    await page.route(url, async (route) => {
      const real = await route.fetch(); // REAL request commits in PostgreSQL.
      committed = { status: real.status(), items: (await real.json()).items };
      await route.abort('failed'); // Lose delivery only, never fulfill a fake success.
    }, { times: 1 });
    await assign.click();
    await expect.poll(() => committed?.status).toBe(200);
    await expect(card.locator('[data-operation-status]').first()).toHaveAttribute('data-tone', 'error');
    const afterLost = inputs('readback');
    expect(afterLost.assignments).toHaveLength(2);
    expect(afterLost.bindings).toHaveLength(2);
    expect(afterLost.cycles).toBe(0);
    events.push({ phase: 'committed_response_aborted', real_response: committed, sql: afterLost });

    await page.reload();
    await expect(card).toBeVisible();
    await select(emails[1]);
    await assign.click();
    await expect(card.locator('[data-operation-status]').first()).toContainText('Уже была назначена: 1');
    for (let i = 0; i < 2; i += 1) {
      const read = await page.request.get(base + '/users/admin/organizations');
      expect(read.status()).toBe(200);
    }
    const final = inputs('readback');
    expect(final).toEqual(afterLost);
    events.push({ phase: 'reload_repeat_readback', sql: final });
    await page.screenshot({ path: path.join(dir, 'assignment-readback.png'), fullPage: true });
  } finally {
    // Preserve primary diagnostics BEFORE deleting only this owned DB.
    fs.writeFileSync(path.join(dir, 'events.json'), JSON.stringify(events, null, 2) + '\n');
    await context?.close();
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
