// Actual HTTP/PostgreSQL regression for Q-DRAFT-01. No successful resolver,
// response/Connection substitution, paid provider, refill workaround or AC18 claim.
import { test, expect } from '@playwright/test';
import { spawn, spawnSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { createHash, randomUUID } from 'node:crypto';
import { persistReceipt } from './fixtures/receipt-file.mjs';

for (const scenario of [
  { name: 'first-three-1440', count: 3, width: 1440 },
  { name: 'first-three-390', count: 3, width: 390 },
  { name: 'all-fields-1440', count: 12, width: 1440 },
  { name: 'read-complete-control', count: 0, width: 1440 },
]) test(`Q-DRAFT-01 actual PG: ${scenario.name} retains input without refill`, async ({ page }) => {
  test.setTimeout(150000);
  if (!process.env.STAND_ADMIN_URL) throw new Error('Explicit isolated STAND_ADMIN_URL required');
  const root = process.cwd(), python = process.env.BROWSER_PYTHON || path.join(root, '.venv/bin/python');
  const directory = path.join(process.env.P4K_EVIDENCE_DIRECTORY || path.join(root, '.test-stand/questionnaire-draft-fix'),
    scenario.name + '-' + randomUUID());
  fs.mkdirSync(directory, { recursive: true });
  const statePath = path.join(directory, 'state.json'), port = '18874', base = `http://127.0.0.1:${port}`;
  const fixture = JSON.parse(fs.readFileSync(path.join(root, 'tests/browser/fixtures/questionnaire-it-synthetic-v1.json'), 'utf8'));
  const entries = Object.entries(fixture.fields).filter(([name]) => name !== 'source_author');
  const save = (name, value) => persistReceipt(path.join(directory, `${name}.json`), value);
  const run = (script, args) => {
    const result = spawnSync(python, [script, ...args], { encoding: 'utf8', timeout: 90000 });
    if (result.status !== 0) throw new Error(`${script}: ${result.stderr}${result.stdout}`);
    return result.stdout;
  };
  const cli = (action) => run('scripts/test_stand.py', [action, '--state', statePath,
    '--port', port, '--gateway', '0', '--provider', 'disabled']);
  const readDb = (id = '0') => JSON.parse(run('tests/questionnaire_it_readback.py', ['--state', statePath, '--revision-id', id]));
  let server, release, held = 0;
  const pending = new Promise((resolve) => { release = resolve; });
  const requests = [];
  page.on('request', (request) => {
    const pathname = new URL(request.url()).pathname;
    if (pathname.startsWith('/users/')) requests.push({ method: request.method(), path: pathname });
  });
  await page.route(/\/users\/admin\/organizations\/\d+\/questionnaire$/, async (route) => {
    held += 1; await pending; await route.continue();
  });
  cli('create');
  try {
    cli('bootstrap'); cli('seed');
    run('scripts/adm28_browser_fixture.py', ['--state', statePath]);
    const state = JSON.parse(fs.readFileSync(statePath, 'utf8'));
    const sources = ['web/js/screens/admin/organizations.js', 'tests/browser/questionnaire-draft-preservation.spec.mjs',
      'tests/browser/fixtures/questionnaire-it-synthetic-v1.json', 'tests/questionnaire_it_readback.py',
      ...fs.readdirSync(path.join(root, 'web/dist')).map((name) => 'web/dist/' + name)];
    save('run', { run_id: state.run_id, database: state.database, scenario, provider_mode: 'disabled',
      gateway: 0, scope: 'FREE_UI_HTTP_PG_REGRESSION_NOT_AC18',
      head: spawnSync('git', ['rev-parse', 'HEAD'], { encoding: 'utf8' }).stdout.trim(),
      source_sha256: Object.fromEntries(sources.map((name) => [name,
        createHash('sha256').update(fs.readFileSync(path.join(root, name))).digest('hex')])) });
    const baseline = readDb(); save('baseline', baseline);
    const fd = fs.openSync(path.join(directory, 'server.log'), 'a');
    server = spawn(python, ['scripts/test_stand.py', 'serve', '--state', statePath], { stdio: ['ignore', fd, fd] });
    fs.closeSync(fd);
    await expect.poll(async () => { try { return (await fetch(base + '/health/ready')).status; } catch { return 0; } },
      { timeout: 30000 }).toBe(200);
    await page.setViewportSize({ width: scenario.width, height: 1000 });
    await page.goto(base);
    await page.locator('#email-input').fill('admin@example.test');
    await page.locator('#request-magic-link-button').click();
    await page.locator('#magic-token-input').fill(state.password);
    await page.locator('#verify-magic-link-button').click();
    await expect(page.locator('#admin-organizations-panel')).toBeVisible();
    await expect.poll(() => held).toBeGreaterThan(0);
    const card = page.locator('.admin-organization-card');
    await card.getByRole('button', { name: 'Данные организации', exact: true }).click();
    const organizationId = await card.getAttribute('data-organization-id');
    const form = card.locator('[data-action="preview-early-data"]');
    const fill = async (items) => { for (const [name, value] of items) await form.locator(`[name="${name}"]`).fill(value); };
    const values = () => form.evaluate((element) => Object.fromEntries(
      [...element.querySelectorAll('input[name]:not([type="hidden"]),textarea[name]')].map((field) => [field.name, field.value])));
    await fill(entries.slice(0, scenario.count));
    const original = await form.elementHandle();
    const before = await values(); save('before-release', { values: before, fields_entered: scenario.count });
    await page.screenshot({ path: path.join(directory, 'before-release.png'), fullPage: true });
    release();
    await expect(card.locator('.admin-questionnaire-load-state').filter({ hasText: 'Для этой организации ещё нет сохранённых анкет.' }).first()).toBeVisible();
    await page.evaluate(() => new Promise(requestAnimationFrame));
    const after = await values(), connected = await original.evaluate((element) => element.isConnected);
    save('after-release', { values: after, original_node_connected: connected, lost_fields: entries.slice(0, scenario.count)
      .filter(([name, value]) => after[name] !== value).map(([name]) => name) });
    for (const [name, value] of entries.slice(0, scenario.count)) expect(after[name]).toBe(value);
    expect(connected).toBe(false); // Still the real renderer, not a frozen test DOM.
    await fill(entries.slice(scenario.count));
    for (const [name, value] of entries) await expect(form.locator(`[name="${name}"]`)).toHaveValue(value);
    expect(await form.evaluate((element) => element.checkValidity())).toBe(true);
    await page.screenshot({ path: path.join(directory, 'after-release.png'), fullPage: true });
    const previewResponse = page.waitForResponse((response) => response.request().method() === 'POST' && response.url().endsWith('/questionnaire/preview'));
    await form.getByRole('button', { name: 'Сохранить черновик и предпросмотр', exact: true }).click();
    expect((await previewResponse).status()).toBe(201);
    const preview = card.locator('.admin-questionnaire-preview');
    await expect(preview).toContainText('Готово к подтверждению');
    const revisionId = await preview.getAttribute('data-questionnaire-revision-id');
    const confirmation = page.waitForResponse((response) => response.request().method() === 'POST' && response.url().endsWith(`/questionnaire/${revisionId}/confirm`));
    await preview.getByRole('button', { name: 'Подтвердить сведения', exact: true }).click();
    expect((await confirmation).status()).toBe(200);
    const response = await page.request.get(`${base}/users/admin/organizations/${organizationId}/questionnaire/${revisionId}`);
    expect(response.status()).toBe(200);
    const http = await response.json(), db = readDb(revisionId);
    save('confirmed-readback', { http, database: db });
    expect(db.revision.status).toBe('confirmed'); expect(db.revision.answers_json).toEqual(http.answers_json);
    expect(db.revision.source_author).toBe('');
    for (const name of ['assignments', 'profiles', 'preparation_operations', 'cycles', 'assessment_situations', 'assessment_answers']) {
      expect(db.counts[name]).toBe(baseline.counts[name]);
    }
    expect(db.counts.questionnaire_revisions).toBe(baseline.counts.questionnaire_revisions + 1);
    await page.reload();
    for (const [name, value] of entries) await expect(form.locator(`[name="${name}"]`)).toHaveValue(value);
    expect(requests.filter((item) => /\/(prepare|start)$/.test(item.path))).toEqual([]);
    save('result', { status: 'PASS_UI_HTTP_PG_NOT_AC18', scenario, retained_fields: scenario.count,
      refill_count: 0, all_12_after_reload: true, preview_status: 201, confirm_status: 200, readback_status: 200,
      provider_operations: 0, real_get_response_unmodified: true, requests,
      historical_ac18_causality: 'NOT_PROVEN', timeout_cleanup_cause: 'UNKNOWN', prep_diag_01: 'UNKNOWN' });
  } catch (error) {
    save('failure', { error: error.message, requests }); throw error;
  } finally {
    release();
    if (server && server.exitCode === null) {
      const exited = new Promise((resolve) => server.once('exit', resolve)); server.kill('SIGTERM');
      await Promise.race([exited, new Promise((resolve) => setTimeout(resolve, 5000))]);
      if (server.exitCode === null) { server.kill('SIGKILL'); await exited; }
    }
    cli('destroy');
  }
});
