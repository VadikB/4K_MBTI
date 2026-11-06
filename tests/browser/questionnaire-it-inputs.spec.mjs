// Free questionnaire-only probe. Actual HTTP/PG, existing synthetic ADM28 inputs.
// Not AC18, not pilot admission, no resolver/Connection replacement or LLM.
import { test, expect } from '@playwright/test';
import { spawn, spawnSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { randomUUID } from 'node:crypto';
import { persistReceipt } from './fixtures/receipt-file.mjs';
import { capturePathViewports } from './fixtures/path-viewports.mjs';

test('IT questionnaire: actual preview, confirmation, reload and PostgreSQL readback', async ({ page }) => {
  test.setTimeout(180000);
  if (!process.env.STAND_ADMIN_URL) throw new Error('Explicit isolated STAND_ADMIN_URL required');
  const root = process.cwd();
  const python = process.env.BROWSER_PYTHON || path.join(root, '.venv/bin/python');
  const directory = path.join(process.env.P4K_EVIDENCE_DIRECTORY || path.join(root, '.test-stand/questionnaire-it'), randomUUID());
  fs.mkdirSync(directory, { recursive: true });
  const statePath = path.join(directory, 'state.json');
  const port = '18873', base = `http://127.0.0.1:${port}`;
  const fixture = JSON.parse(fs.readFileSync(path.join(root,
    'tests/browser/fixtures/questionnaire-it-synthetic-v1.json'), 'utf8'));
  const values = fixture.fields;
  const save = (name, value) => persistReceipt(path.join(directory, `${name}.json`), value);
  const run = (script, args) => {
    const result = spawnSync(python, [script, ...args], { encoding: 'utf8', timeout: 90000 });
    if (result.status !== 0) throw new Error(`${script}: ${result.stderr}${result.stdout}`);
    return result.stdout;
  };
  const cli = (action) => run('scripts/test_stand.py', [action, '--state', statePath,
    '--port', port, '--gateway', '0', '--provider', 'disabled']);
  let server;
  const requests = [];
  page.on('request', (request) => {
    const pathname = new URL(request.url()).pathname;
    if (pathname.startsWith('/users/')) requests.push({ method: request.method(), path: pathname });
  });
  cli('create');
  try {
    cli('bootstrap');
    cli('seed');
    run('scripts/adm28_browser_fixture.py', ['--state', statePath]);
    const baseline = JSON.parse(run('tests/questionnaire_it_readback.py', ['--state', statePath, '--revision-id', '0']));
    save('baseline', baseline);
    const state = JSON.parse(fs.readFileSync(statePath, 'utf8'));
    save('run', { run_id: state.run_id, database: state.database,
      scope: fixture.scope, provider_mode: 'disabled', gateway: 0, fixture,
      code_sha: spawnSync('git', ['rev-parse', 'HEAD'], { encoding: 'utf8' }).stdout.trim() });
    const fd = fs.openSync(path.join(directory, 'server.log'), 'a');
    server = spawn(python, ['scripts/test_stand.py', 'serve', '--state', statePath], { stdio: ['ignore', fd, fd] });
    fs.closeSync(fd);
    await expect.poll(async () => {
      try { return (await fetch(base + '/health/ready')).status; } catch { return 0; }
    }, { timeout: 30000 }).toBe(200);
    await page.goto(base);
    await page.locator('#email-input').fill('admin@example.test');
    await page.locator('#request-magic-link-button').click();
    await page.locator('#magic-token-input').fill(state.password);
    await page.locator('#verify-magic-link-button').click();
    await expect(page.locator('#admin-organizations-panel')).toBeVisible();
    const card = page.locator('.admin-organization-card');
    await card.getByRole('button', { name: 'Данные организации', exact: true }).click();
    const organizationId = await card.getAttribute('data-organization-id');
    // A real completed card-save/readback provides an explicit initialization
    // boundary. This is NOT a fix or a claimed explanation of the historical race.
    const profile = card.locator('[data-action="update-profile"]');
    await profile.locator('[name="name"]').fill(values.organization_name);
    await profile.getByRole('button', { name: 'Сохранить карточку', exact: true }).click();
    await expect(profile.locator('[data-operation-status]')).toContainText('Карточка организации сохранена');
    await expect(card.locator('.admin-questionnaire-load-state').filter({ hasText: 'Загружаем' })).toHaveCount(0);
    const form = card.locator('[data-action="preview-early-data"]');
    await expect(form.locator('[name="assignment_ref"]')).toHaveValue('ADM28 isolated');
    for (const [name, value] of Object.entries(values)) await form.locator(`[name="${name}"]`).fill(value);
    const assertValues = async () => {
      for (const [name, value] of Object.entries(values)) await expect(form.locator(`[name="${name}"]`)).toHaveValue(value);
    };
    await assertValues();
    await capturePathViewports(page, directory, 'it-questionnaire', [
      { name: 'author', locator: form.locator('[name="source_author"]') },
      { name: 'organization-name', locator: form.locator('[name="organization_name"]') },
      { name: 'organization-type', locator: form.locator('[name="organization_type"]') },
      { name: 'preview', locator: form.getByRole('button', { name: 'Сохранить черновик и предпросмотр', exact: true }) },
    ]);
    await assertValues();
    save('filled-fields', { values, all_12_fields_retained: true, viewport_widths: [1440, 320, 390, 768] });
    const previewResponse = page.waitForResponse((response) => response.request().method() === 'POST'
      && response.url().endsWith(`/users/admin/organizations/${organizationId}/questionnaire/preview`));
    await form.getByRole('button', { name: 'Сохранить черновик и предпросмотр', exact: true }).click();
    expect((await previewResponse).status()).toBe(201);
    const preview = card.locator('.admin-questionnaire-preview');
    await expect(preview).toContainText('Готово к подтверждению');
    const revisionId = await preview.getAttribute('data-questionnaire-revision-id');
    const confirmResponse = page.waitForResponse((response) => response.request().method() === 'POST'
      && response.url().endsWith(`/questionnaire/${revisionId}/confirm`));
    await preview.getByRole('button', { name: 'Подтвердить сведения', exact: true }).click();
    expect((await confirmResponse).status()).toBe(200);
    await expect(card.locator('.admin-questionnaire-confirmation')).toContainText('Сведения подтверждены');
    const getRevision = () => page.request.get(`${base}/users/admin/organizations/${organizationId}/questionnaire/${revisionId}`);
    const response = await getRevision();
    expect(response.status()).toBe(200);
    const saved = await response.json();
    save('http-readback', saved);
    expect(saved.status).toBe('confirmed');
    expect(saved.source_author).toBe(values.source_author);
    expect(saved.answers_json.C01.name).toBe(values.organization_name);
    expect(saved.answers_json.C01.organization_type).toBe(values.organization_type);
    await page.screenshot({ path: path.join(directory, 'confirmed-1440.png'), fullPage: true });
    await page.reload();
    await expect(form.locator('[name="source_author"]')).toHaveValue(values.source_author);
    await assertValues();
    const db = JSON.parse(run('tests/questionnaire_it_readback.py', ['--state', statePath, '--revision-id', revisionId]));
    save('database-readback', db);
    expect(db.revision.status).toBe('confirmed');
    expect(db.revision.source_author).toBe(saved.source_author);
    expect(db.revision.answers_json).toEqual(saved.answers_json);
    for (const name of ['assignments', 'profiles', 'preparation_operations', 'cycles', 'assessment_situations', 'assessment_answers']) {
      expect(db.counts[name], `${name}: unchanged since synthetic seed`).toBe(baseline.counts[name]);
    }
    expect(db.counts.questionnaire_revisions).toBe(baseline.counts.questionnaire_revisions + 1);
    expect(requests.filter((item) => /\/(?:prepare|start)$/.test(item.path))).toEqual([]);
    save('result', { status: 'PASS_QUESTIONNAIRE_ONLY', scope: fixture.scope,
      actual_http: true, actual_postgresql: true, mock_resolver: false,
      preview_status: 201, confirm_status: 200, http_readback: saved, database_readback: db, baseline,
      all_12_fields_after_reload: true, requests, provider_operations: 0,
      historical_field_loss_root_cause: 'UNKNOWN', ac18: 'BLOCKED_NOT_REPEATED' });
  } catch (error) {
    save('failure', { error: error.message, requests });
    throw error;
  } finally {
    if (server && server.exitCode === null) {
      const exited = new Promise((resolve) => server.once('exit', resolve));
      server.kill('SIGTERM');
      await Promise.race([exited, new Promise((resolve) => setTimeout(resolve, 5000))]);
      if (server.exitCode === null) { server.kill('SIGKILL'); await exited; }
    }
    cli('destroy');
  }
});
