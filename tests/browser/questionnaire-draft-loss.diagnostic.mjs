// Actual UI/HTTP/PostgreSQL diagnostic: delay only a real GET; no fake response,
// resolver, Connection, product-method override, paid provider or PATH acceptance.
import { test, expect } from '@playwright/test';
import { spawn, spawnSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { createHash, randomUUID } from 'node:crypto';
import { persistReceipt } from './fixtures/receipt-file.mjs';

const scenarios = [
  { name: 'first-three-1440', count: 3, width: 1440 },
  { name: 'first-three-390', count: 3, width: 390 },
  { name: 'all-fields-1440', count: 12, width: 1440 },
  { name: 'read-complete-control', count: 0, width: 1440 },
];

for (const scenario of scenarios) test(`DIAGNOSE draft loss: ${scenario.name}`, async ({ page }) => {
  if (!process.env.STAND_ADMIN_URL) throw new Error('Explicit isolated STAND_ADMIN_URL required');
  const root = process.cwd();
  const python = process.env.BROWSER_PYTHON || path.join(root, '.venv/bin/python');
  const directory = path.join(process.env.P4K_EVIDENCE_DIRECTORY || path.join(root, '.test-stand/questionnaire-draft-loss'),
    scenario.name + '-' + randomUUID());
  fs.mkdirSync(directory, { recursive: true });
  const statePath = path.join(directory, 'state.json');
  const port = '18874', base = `http://127.0.0.1:${port}`;
  const fixture = JSON.parse(fs.readFileSync(path.join(root, 'tests/browser/fixtures/questionnaire-it-synthetic-v1.json'), 'utf8'));
  const entries = Object.entries(fixture.fields);
  const save = (name, value) => persistReceipt(path.join(directory, `${name}.json`), value);
  const run = (script, args) => {
    const result = spawnSync(python, [script, ...args], { encoding: 'utf8', timeout: 90000 });
    if (result.status !== 0) throw new Error(`${script}: ${result.stderr}${result.stdout}`);
    return result.stdout;
  };
  const cli = (action) => run('scripts/test_stand.py', [action, '--state', statePath,
    '--port', port, '--gateway', '0', '--provider', 'disabled']);
  const readDb = (id = '0') => JSON.parse(run('tests/questionnaire_it_readback.py', ['--state', statePath, '--revision-id', id]));
  let server, release;
  const pending = new Promise((resolve) => { release = resolve; });
  let readRequests = 0;
  const timeline = [];
  const record = (event, data = {}) => timeline.push({ event, at: new Date().toISOString(), ...data });
  page.on('request', (request) => {
    const pathname = new URL(request.url()).pathname;
    if (pathname.startsWith('/users/')) record('request', { method: request.method(), path: pathname });
  });
  page.on('response', (response) => {
    const pathname = new URL(response.url()).pathname;
    if (pathname.startsWith('/users/')) record('response', { method: response.request().method(), path: pathname, status: response.status() });
  });
  await page.route(/\/users\/admin\/organizations\/\d+\/questionnaire$/, async (route) => {
    readRequests += 1;
    record('real_questionnaire_get_held');
    await pending;
    record('real_questionnaire_get_continued');
    await route.continue();
  });
  cli('create');
  try {
    cli('bootstrap'); cli('seed');
    run('scripts/adm28_browser_fixture.py', ['--state', statePath]);
    const state = JSON.parse(fs.readFileSync(statePath, 'utf8'));
    const sources = ['web/js/screens/admin/organizations.js', 'web/js/wiring.js',
      'web/js/entries/admin-organizations.js', 'tests/browser/questionnaire-draft-loss.diagnostic.mjs',
      'tests/browser/questionnaire-draft-loss.config.mjs', 'tests/browser/fixtures/questionnaire-it-synthetic-v1.json',
      'tests/questionnaire_it_readback.py', ...fs.readdirSync(path.join(root, 'web/dist')).map((name) => 'web/dist/' + name)];
    save('run', { run_id: state.run_id, database: state.database, scenario,
      scope: 'DIAGNOSTIC_NOT_PRODUCT_PASS_NOT_AC18', provider_mode: 'disabled', gateway: 0,
      head: spawnSync('git', ['rev-parse', 'HEAD'], { encoding: 'utf8' }).stdout.trim(),
      source_sha256: Object.fromEntries(sources.map((name) => [name,
        createHash('sha256').update(fs.readFileSync(path.join(root, name))).digest('hex')])) });
    const baseline = readDb(); save('baseline', baseline);
    const fd = fs.openSync(path.join(directory, 'server.log'), 'a');
    server = spawn(python, ['scripts/test_stand.py', 'serve', '--state', statePath], { stdio: ['ignore', fd, fd] });
    fs.closeSync(fd);
    await expect.poll(async () => {
      try { return (await fetch(base + '/health/ready')).status; } catch { return 0; }
    }, { timeout: 30000 }).toBe(200);
    await page.setViewportSize({ width: scenario.width, height: 1000 });
    await page.goto(base);
    await page.locator('#email-input').fill('admin@example.test');
    await page.locator('#request-magic-link-button').click();
    await page.locator('#magic-token-input').fill(state.password);
    await page.locator('#verify-magic-link-button').click();
    await expect(page.locator('#admin-organizations-panel')).toBeVisible();
    await expect.poll(() => readRequests).toBeGreaterThan(0);
    const card = page.locator('.admin-organization-card');
    await card.getByRole('button', { name: 'Данные организации', exact: true }).click();
    const organizationId = await card.getAttribute('data-organization-id');
    const form = card.locator('[data-action="preview-early-data"]');
    const values = () => form.evaluate((element) => Object.fromEntries(
      [...element.querySelectorAll('input[name]:not([type="hidden"]),textarea[name]')].map((field) => [field.name, field.value])));
    const fill = async (items) => {
      for (const [name, value] of items) await form.locator(`[name="${name}"]`).fill(value);
    };
    await fill(entries.slice(0, scenario.count));
    const original = await form.elementHandle();
    const before = await values(); record('before_release', { values: before });
    save('before-release', { values: before, fields_entered: scenario.count, read_pending: true });
    await page.screenshot({ path: path.join(directory, 'before-release.png'), fullPage: true });
    release();
    await expect(card.locator('.admin-questionnaire-load-state').filter({ hasText: 'Для этой организации ещё нет сохранённых анкет.' }).first()).toBeVisible();
    await page.evaluate(() => new Promise(requestAnimationFrame));
    const after = await values();
    const originalConnected = await original.evaluate((element) => element.isConnected);
    const lost = entries.slice(0, scenario.count).filter(([name, value]) => after[name] !== value).map(([name]) => name);
    record('after_release', { values: after, original_node_connected: originalConnected, lost_fields: lost });
    save('after-release', { values: after, original_node_connected: originalConnected, lost_fields: lost });
    await fill(entries.slice(scenario.count));
    const validity = await form.evaluate((element) => ({ valid: element.checkValidity(),
      invalid_fields: [...element.elements].filter((field) => field.willValidate && !field.validity.valid)
        .map((field) => ({ name: field.name, value_missing: field.validity.valueMissing })) }));
    const incomplete = await values();
    save('form-before-preview', { values: incomplete, validity });
    await page.screenshot({ path: path.join(directory, 'after-release.png'), fullPage: true });
    if (scenario.count) {
      await form.getByRole('button', { name: 'Сохранить черновик и предпросмотр', exact: true }).click();
      const noPost = !timeline.some((event) => event.event === 'request' && event.method === 'POST' && event.path.endsWith('/questionnaire/preview'));
      const noConfirm = await card.locator('.admin-questionnaire-preview [data-action="confirm-questionnaire"]').count() === 0;
      const beforeRefill = readDb();
      save('blocked-before-refill', { no_preview_post: noPost, no_confirm_button: noConfirm,
        database_readback: beforeRefill, timeline });
      expect(validity.valid).toBe(false);
      expect(validity.invalid_fields).toContainEqual({ name: 'source_author', value_missing: true });
      expect(noPost).toBe(true); expect(noConfirm).toBe(true);
      expect(beforeRefill.counts).toEqual(baseline.counts);
      expect(lost).toEqual(entries.slice(0, scenario.count).map(([name]) => name));
      expect(originalConnected).toBe(false);
      await fill(entries.slice(0, scenario.count));
    } else {
      expect(validity.valid).toBe(true);
    }
    // Refill is an explicit user workaround, not a product or harness fix.
    for (const [name, value] of entries) await expect(form.locator(`[name="${name}"]`)).toHaveValue(value);
    const previewResponse = page.waitForResponse((response) => response.request().method() === 'POST' && response.url().endsWith('/questionnaire/preview'));
    await form.getByRole('button', { name: 'Сохранить черновик и предпросмотр', exact: true }).click();
    expect((await previewResponse).status()).toBe(201);
    const preview = card.locator('.admin-questionnaire-preview');
    await expect(preview).toContainText('Готово к подтверждению');
    const revisionId = await preview.getAttribute('data-questionnaire-revision-id');
    const confirmation = page.waitForResponse((response) => response.request().method() === 'POST' && response.url().endsWith(`/questionnaire/${revisionId}/confirm`));
    await preview.getByRole('button', { name: 'Подтвердить сведения', exact: true }).click();
    expect((await confirmation).status()).toBe(200);
    const httpResponse = await page.request.get(`${base}/users/admin/organizations/${organizationId}/questionnaire/${revisionId}`);
    expect(httpResponse.status()).toBe(200);
    const http = await httpResponse.json(), db = readDb(revisionId);
    save('confirmed-readback', { http, database: db });
    expect(db.revision.status).toBe('confirmed');
    expect(db.revision.answers_json).toEqual(http.answers_json);
    expect(db.revision.source_author).toBe(fixture.fields.source_author);
    for (const name of ['assignments', 'profiles', 'preparation_operations', 'cycles', 'assessment_situations', 'assessment_answers']) {
      expect(db.counts[name]).toBe(baseline.counts[name]);
    }
    expect(db.counts.questionnaire_revisions).toBe(baseline.counts.questionnaire_revisions + 1);
    expect(timeline.filter((event) => event.event === 'request' && /\/(prepare|start)$/.test(event.path))).toEqual([]);
    save('diagnostic-result', { diagnostic_status: 'COMPLETED',
      product_status: scenario.count ? 'FAIL_DRAFT_LOSS_REPRODUCED' : 'PASS_CONTROL_AFTER_READ_COMPLETE',
      scenario, lost_fields: lost, original_node_connected: originalConnected, validity_before_refill: validity,
      real_get_response_unmodified: true, actual_http_postgresql: true, provider_operations: 0,
      historical_ac18_causal_identity: 'NOT_PROVEN_NO_HISTORICAL_TIMELINE',
      historical_timeout_cleanup_cause: 'UNKNOWN', prep_diag_01: 'UNKNOWN', timeline });
  } catch (error) {
    save('failure', { error: error.message, timeline });
    throw error;
  } finally {
    release();
    if (server && server.exitCode === null) {
      const exited = new Promise((resolve) => server.once('exit', resolve));
      server.kill('SIGTERM');
      await Promise.race([exited, new Promise((resolve) => setTimeout(resolve, 5000))]);
      if (server.exitCode === null) { server.kill('SIGKILL'); await exited; }
    }
    cli('destroy');
  }
});
