// One owned synthetic UI/HTTP/PG run for F23 + F10 + F11 + INT; no provider or EXEC.
import { test, expect } from '@playwright/test';
import { spawn, spawnSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { randomUUID } from 'node:crypto';

test('F23/F10/F11: superadmin connects A, grants U, U assigns self, A survives B and revoke', async ({ browser }) => {
  test.setTimeout(240000);
  if (!process.env.STAND_ADMIN_URL) throw new Error('Explicit isolated STAND_ADMIN_URL required');
  const root = process.cwd();
  const python = process.env.BROWSER_PYTHON || path.join(root, '.venv/bin/python');
  const port = process.env.P4K_F23_PORT || '18977';
  const base = `http://127.0.0.1:${port}`;
  const directory = path.resolve(process.env.P4K_EVIDENCE_DIRECTORY || '.test-stand/f23-f10-f11', randomUUID());
  fs.mkdirSync(directory, { recursive: true });
  const statePath = path.join(directory, 'state.json');
  const save = (name, value) => fs.writeFileSync(path.join(directory, `${name}.json`), JSON.stringify(value, null, 2) + '\n');
  const run = (script, args) => {
    const result = spawnSync(python, [script, ...args], { cwd: root, encoding: 'utf8', timeout: 180000 });
    if (result.status !== 0) throw new Error(`${script} exit ${result.status}: ${result.stderr}`);
    return result.stdout.trim();
  };
  const cli = (action) => run('scripts/test_stand.py', [action, '--state', statePath,
    '--port', port, '--gateway', '0', '--provider', 'disabled']);
  const fixture = (action) => JSON.parse(run('tests/f23_f10_f11_browser_fixture.py',
    [action, '--state', statePath]));
  const superContext = await browser.newContext();
  const userContext = await browser.newContext();
  const superPage = await superContext.newPage();
  const userPage = await userContext.newPage();
  let created = false;
  let server;
  try {
    cli('create'); created = true;
    const state = JSON.parse(fs.readFileSync(statePath, 'utf8'));
    state.browser_scenario = 'acceptance-v1';
    state.browser_case = 'specialist';
    fs.writeFileSync(statePath, JSON.stringify(state));
    cli('bootstrap');
    cli('seed');
    expect(fixture('publish')).toEqual({ program_versions: ['1.0', '2.0'], published: true });
    const prepared = JSON.parse(fs.readFileSync(statePath, 'utf8'));
    const data = prepared.f23_f10_f11;
    const [programA, programB] = data.programs;
    const orgId = data.organization_id;
    save('source', { code_sha: spawnSync('git', ['rev-parse', 'HEAD'], { cwd: root, encoding: 'utf8' }).stdout.trim(),
      programs: data.programs, organization_id: orgId, control_organization_id: data.control_organization_id,
      user_id: data.user_id, provider_mode: prepared.provider_mode });
    const baseline = fixture('readback');
    expect(baseline.membership).toEqual({ role: 'member', is_participant: true });
    expect(baseline.connections).toHaveLength(0);
    expect(baseline.cycles).toHaveLength(0);
    expect(baseline.superadmin_memberships).toBe(0);
    save('baseline', baseline);

    const fd = fs.openSync(path.join(directory, 'server.log'), 'a');
    server = spawn(python, ['scripts/test_stand.py', 'serve', '--state', statePath], {
      cwd: root, stdio: ['ignore', fd, fd],
    });
    fs.closeSync(fd);
    await expect.poll(async () => { try { return (await fetch(base + '/health/ready')).status; } catch { return 0; } },
      { timeout: 30000 }).toBe(200);

    await superPage.goto(base);
    await superPage.locator('#email-input').fill('superadmin@example.test');
    await superPage.locator('#request-magic-link-button').click();
    await superPage.locator('#magic-token-input').fill(prepared.password);
    await superPage.locator('#verify-magic-link-button').click();
    await superPage.getByRole('button', { name: 'Организации', exact: true }).click();
    await expect(superPage.locator('#admin-organizations-panel')).toBeVisible();
    await superPage.locator('#admin-organization-select').selectOption(String(orgId));
    const superCard = superPage.locator(`[data-organization-id="${orgId}"]`);
    await expect(superCard).toBeVisible();
    const connect = superCard.locator('form[data-action="connect-assessment-program"]');
    await connect.locator('[name="program_definition_id"]').selectOption(String(programA.id));
    await connect.getByRole('button', { name: 'Подключить', exact: true }).click();
    await expect(connect).toContainText('Синтетическая программа 1.0');
    const grant = superCard.locator('form[data-action="add-admin"]');
    await grant.locator('input[type="email"]').fill('participant@example.test');
    await grant.getByRole('button', { name: 'Добавить', exact: true }).click();
    await expect(grant).toContainText('Администратор добавлен.');
    const grantListingResponse = await superPage.request.get(`${base}/users/admin/organizations`);
    expect(grantListingResponse.status()).toBe(200);
    const grantListing = await grantListingResponse.json();
    expect(grantListing.items.find((org) => org.id === orgId)?.admins)
      .toContainEqual(expect.objectContaining({ email: 'participant@example.test' }));
    const revoke = superCard.locator('button[data-action="delete-admin"][data-value="participant@example.test"]');
    await expect(revoke).toBeVisible();
    const afterGrant = fixture('readback');
    expect(afterGrant.membership).toEqual({ role: 'admin', is_participant: true });
    expect(afterGrant.superadmin_memberships).toBe(0);
    save('after-grant', afterGrant);

    await userPage.goto(base);
    await userPage.locator('#email-input').fill('participant@example.test');
    await userPage.locator('#request-magic-link-button').click();
    await userPage.locator('#magic-token-input').fill(prepared.password);
    await userPage.locator('#verify-magic-link-button').click();
    await expect(userPage.locator('#admin-organizations-panel')).toBeVisible();
    const userCard = userPage.locator(`[data-organization-id="${orgId}"]`);
    await expect(userCard).toContainText('Синтетическая программа 1.0');
    await expect(userPage.locator(`[data-organization-id="${data.control_organization_id}"]`)).toHaveCount(0);
    await expect(userCard.locator('form[data-action="connect-assessment-program"]')).toHaveCount(0);
    const foreign = await userPage.request.get(`${base}/users/admin/organizations/${data.control_organization_id}/assessment-program`);
    expect(foreign.status()).toBe(403);
    const forbidden = await userPage.request.put(`${base}/users/admin/organizations/${orgId}/assessment-program`, {
      data: { program_definition_id: programB.id, operation_id: 'forbidden-org-admin' },
    });
    expect(forbidden.status()).toBe(403);

    await userCard.getByRole('button', { name: 'Данные организации', exact: true }).click();
    const form = userCard.locator('form[data-action="preview-early-data"]');
    const fields = { organization_name: 'Синтетическая организация', organization_type: 'Компания',
      industry: 'ИТ', activity_description: 'Синтетическая проверка', purpose: 'Синтетическая цель',
      results_usage: 'Для развития', result_recipients: 'Участник', organizer: 'Синтетический HR',
      responsible_contact: 'participant@example.test', case_reality_level: 'Реальные',
      organization_name_usage_rules: 'Разрешено' };
    for (const [name, value] of Object.entries(fields)) await form.locator(`[name="${name}"]`).fill(value);
    await form.getByRole('button', { name: 'Сохранить черновик и предпросмотр' }).click();
    const preview = userCard.locator('.admin-questionnaire-preview');
    await expect(preview).toContainText('Готово к подтверждению');
    await preview.getByRole('button', { name: 'Подтвердить сведения' }).click();
    await expect(userCard.locator('.admin-questionnaire-confirmation')).toContainText('Сведения подтверждены');
    await userCard.getByRole('button', { name: 'Участники оценки', exact: true }).click();
    await userCard.locator('input[name="invitation_email"][value="participant@example.test"]').check();
    await userCard.getByRole('button', { name: 'Назначить оценку', exact: true }).click();
    await expect(userCard.locator('[data-operation-status]')).toContainText('оценка назначена');
    const afterAssignment = fixture('readback');
    expect(afterAssignment.assignment).toBeTruthy();
    expect(afterAssignment.binding).toBeTruthy();
    expect(afterAssignment.cycles).toHaveLength(0);
    save('after-assignment', afterAssignment);

    await userPage.getByRole('button', { name: 'Моя оценка', exact: true }).click();
    await expect(userPage.locator('#onboarding-panel')).toBeVisible();
    await userPage.reload();
    await expect(userPage.locator('#onboarding-panel')).toBeVisible();
    await userPage.getByRole('button', { name: 'Управление', exact: true }).click();
    await expect(userPage.locator('#admin-organizations-panel')).toBeVisible();
    expect(fixture('readback').cycles).toHaveLength(0);

    expect(fixture('seed-cycle')).toEqual({ synthetic_saved_cycle: true });
    const frozen = fixture('readback');
    expect(frozen.cycles).toHaveLength(1);
    save('saved-a', frozen);
    await connect.locator('[name="program_definition_id"]').selectOption(String(programB.id));
    await connect.getByRole('button', { name: 'Подключить', exact: true }).click();
    await expect(connect).toContainText('Синтетическая программа 2.0');
    await userPage.reload();
    await expect(userPage.locator(`[data-organization-id="${orgId}"]`)).toContainText('Синтетическая программа 2.0');
    const switched = fixture('readback');
    expect(switched.connections).toHaveLength(2);
    expect(switched.connections.map((row) => row.program_definition_id)).toEqual([programA.id, programB.id]);
    expect(switched.connections.map((row) => row.is_current)).toEqual([false, true]);
    expect(switched.connections[0].superseded).toBe(true);
    expect(switched.assignment).toEqual(frozen.assignment);
    expect(switched.binding).toEqual(frozen.binding);
    expect(switched.cycles).toEqual(frozen.cycles);
    expect(switched.control_connections).toBe(0);
    save('switched-b', switched);

    await expect(revoke).toBeVisible();
    superPage.once('dialog', (dialog) => dialog.accept());
    await revoke.click();
    await expect(revoke).toHaveCount(0);
    await expect(superCard).toContainText('Права администратора сняты.');
    await expect.poll(() => fixture('readback').membership.role).toBe('member');
    const revoked = fixture('readback');
    expect(revoked.membership.is_participant).toBe(true);
    expect(revoked.assignment).toEqual(frozen.assignment);
    expect(revoked.binding).toEqual(frozen.binding);
    expect(revoked.cycles).toEqual(frozen.cycles);
    expect(revoked.superadmin_memberships).toBe(0);
    expect(revoked.control_connections).toBe(0);
    save('revoked', revoked);
  } finally {
    try {
      await Promise.allSettled([superContext.close(), userContext.close()]);
    } finally {
      try {
        if (server && server.exitCode === null) {
          const exited = new Promise((resolve) => server.once('exit', resolve));
          server.kill('SIGTERM');
          await Promise.race([exited, new Promise((resolve) => setTimeout(resolve, 5000))]);
          if (server.exitCode === null) { server.kill('SIGKILL'); await exited; }
        }
      } finally {
        if (created) cli('destroy');
      }
    }
  }
});
