// Standalone narrow positive probe for P4K-ADM-PROGRAM-UI-FIX-01.
// Run from the repository root. This file does not import the full PATH runner.
// ADM28 is an existing synthetic upstream program/org fixture; questionnaire
// preview and confirmation below are real UI actions against owned HTTP + PG.
import fs from 'node:fs';
import path from 'node:path';
import { createHash, randomUUID } from 'node:crypto';
import { createRequire } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { spawn, spawnSync } from 'node:child_process';

const root = process.cwd();
const require = createRequire(path.join(root, 'package.json'));
const { test, expect } = require('@playwright/test');
const { persistReceipt } = await import(pathToFileURL(path.join(root,
  'tests/browser/fixtures/receipt-file.mjs')).href);
const python = process.env.BROWSER_PYTHON || path.join(root, '.venv/bin/python');
const port = Number(process.env.P4K_ADM_POSITIVE_PORT || '18943');
if (!Number.isInteger(port) || port < 1024 || port > 65535) throw new Error('Invalid P4K_ADM_POSITIVE_PORT');
const base = `http://127.0.0.1:${port}`;
const fixtureRelative = 'tests/browser/fixtures/questionnaire-it-synthetic-v1.json';
const csvRelative = 'assessment_definitions/questionnaires/corporate/0.1/example.synthetic.csv';
const fixture = JSON.parse(fs.readFileSync(path.join(root, fixtureRelative), 'utf8'));
const csvText = fs.readFileSync(path.join(root, csvRelative), 'utf8');
const unchangedCounts = ['assignments', 'profiles', 'preparation_operations', 'cycles',
  'assessment_situations', 'assessment_answers'];

test.describe.configure({ mode: 'serial' });

for (const channel of ['product_form', 'csv']) {
  test(`ADM-PROGRAM actual owned HTTP+PG: ${channel} preview → exact revision → confirm → readback`, async ({ page }, info) => {
    test.setTimeout(180000);
    if (!process.env.STAND_ADMIN_URL) throw new Error('Explicit isolated STAND_ADMIN_URL required');
    info.annotations.push({ type: 'actual_http_postgresql',
      description: 'Narrow questionnaire-only probe; real auth/router/PG; provider disabled; no PATH, EXEC, reports or LLM.' });
    info.annotations.push({ type: 'synthetic_upstream',
      description: 'Existing ADM28 fixture supplies org/admin/published program connection only; it does not create the tested questionnaire.' });
    const directory = path.resolve(process.env.P4K_EVIDENCE_DIRECTORY || '.test-stand/adm-program-positive',
      `${channel}-${randomUUID()}`);
    fs.mkdirSync(directory, { recursive: true });
    const statePath = path.join(directory, 'state.json');
    const files = {};
    const save = (name, value) => {
      files[`${name}.json`] = persistReceipt(path.join(directory, `${name}.json`), value);
    };
    const run = (script, args) => {
      const result = spawnSync(python, [script, ...args], {
        cwd: root, encoding: 'utf8', timeout: 120000,
      });
      fs.appendFileSync(path.join(directory, 'stand.log'), `${script}: ${result.stdout || ''}${result.stderr || ''}`);
      if (result.status !== 0) throw new Error(`${script} failed (exit ${result.status}); see stand.log`);
      return result.stdout;
    };
    const cli = (action) => run('scripts/test_stand.py', [action, '--state', statePath,
      '--port', String(port), '--gateway', '0', '--provider', 'disabled']);
    const readDb = (id = 0) => JSON.parse(run('tests/questionnaire_it_readback.py',
      ['--state', statePath, '--revision-id', String(id)]));
    const requests = [];
    const responses = [];
    page.on('request', (request) => {
      const pathname = new URL(request.url()).pathname;
      if (pathname.startsWith('/users/')) requests.push({ method: request.method(), path: pathname });
    });
    page.on('response', (response) => {
      const pathname = new URL(response.url()).pathname;
      if (pathname.startsWith('/users/')) responses.push({ method: response.request().method(), path: pathname,
        status: response.status() });
    });
    let created = false;
    let server;
    let revisionId = 0;
    let failure;
    try {
      cli('create'); created = true;
      cli('bootstrap');
      cli('seed');
      run('scripts/adm28_browser_fixture.py', ['--state', statePath]);
      const baseline = readDb();
      save('baseline', baseline);
      const state = JSON.parse(fs.readFileSync(statePath, 'utf8'));
      const git = (args) => spawnSync('git', args, { cwd: root, encoding: 'utf8' }).stdout.trim();
      const sourceFiles = [fixtureRelative, csvRelative, 'scripts/test_stand.py',
        'scripts/adm28_browser_fixture.py', 'tests/questionnaire_it_readback.py',
        'web/js/screens/admin/organizations.js', 'web/js/wiring.js', 'web/js/config.js'];
      save('run', { scope: 'local_synthetic_questionnaire_only', channel, run_id: state.run_id,
        database: state.database, provider_mode: state.provider_mode, gateway: state.gateway,
        source_head_sha: git(['rev-parse', 'HEAD']), worktree_dirty: Boolean(git(['status', '--porcelain'])),
        fixture: { id: fixture.id, version: fixture.version },
        source_sha256: Object.fromEntries(sourceFiles.map((name) => [name,
          createHash('sha256').update(fs.readFileSync(path.join(root, name))).digest('hex')])),
        probe_sha256: createHash('sha256').update(fs.readFileSync(fileURLToPath(import.meta.url))).digest('hex'),
        credentials_exported: false, tested_actions_replaced_with_sql: false });
      expect(state.provider_mode).toBe('disabled');
      expect(state.gateway).toBe(0);
      const fd = fs.openSync(path.join(directory, 'server.log'), 'a');
      server = spawn(python, ['scripts/test_stand.py', 'serve', '--state', statePath], {
        cwd: root, stdio: ['ignore', fd, fd],
      });
      fs.closeSync(fd);
      await expect.poll(async () => {
        try { return (await fetch(`${base}/health/ready`)).status; } catch { return 0; }
      }, { timeout: 30000 }).toBe(200);
      await page.goto(base);
      await page.locator('#email-input').fill('admin@example.test');
      await page.locator('#request-magic-link-button').click();
      await page.locator('#magic-token-input').fill(state.password);
      await page.locator('#verify-magic-link-button').click();
      await expect(page.locator('#admin-organizations-panel')).toBeVisible();
      const card = page.locator('.admin-organization-card');
      await expect(card).toHaveCount(1);
      const organizationId = await card.getAttribute('data-organization-id');
      await expect(card.locator('.admin-assignment-readiness')).toContainText('ADM28 synthetic Specialist pilot');
      await card.locator('[data-action="show-admin-view"][data-view="organization-data"]').click();
      const profile = card.locator('[data-action="update-profile"]');
      await profile.locator('[name="name"]').fill(fixture.fields.organization_name);
      await profile.getByRole('button', { name: 'Сохранить карточку', exact: true }).click();
      await expect(profile.locator('[data-operation-status]')).toContainText('Карточка организации сохранена');
      await expect(card.locator('.admin-questionnaire-load-state').filter({ hasText: 'Загружаем' })).toHaveCount(0);
      const connectionResponse = await page.request.get(`${base}/users/admin/organizations/${organizationId}/assessment-program`);
      expect(connectionResponse.status()).toBe(200);
      save('program-readback', await connectionResponse.json());
      if (channel === 'csv') {
        await card.locator('[data-action="show-admin-view"][data-view="questionnaire"]').click();
      }
      const form = card.locator(`[data-action="${channel === 'csv' ? 'preview-questionnaire' : 'preview-early-data'}"]`);
      await expect(form).toBeVisible();
      await expect(form.locator('[name="assignment_ref"]')).toHaveAttribute('type', 'hidden');
      await expect(form.locator('[name="assignment_ref"]')).toHaveValue('ADM28 isolated');
      const sourceAuthor = channel === 'csv' ? `${fixture.fields.source_author} · CSV` : fixture.fields.source_author;
      if (channel === 'product_form') {
        for (const [name, value] of Object.entries(fixture.fields)) await form.locator(`[name="${name}"]`).fill(value);
      } else {
        await form.locator('[name="source_author"]').fill(sourceAuthor);
        await form.locator('[name="csv"]').setInputFiles({ name: 'example.synthetic.csv',
          mimeType: 'text/csv', buffer: Buffer.from(csvText) });
      }
      await page.screenshot({ path: path.join(directory, 'filled-1440.png'), fullPage: true });
      const previewResponse = page.waitForResponse((response) => response.request().method() === 'POST'
        && response.url().endsWith(`/users/admin/organizations/${organizationId}/questionnaire/preview`));
      await form.getByRole('button', { name: channel === 'csv' ? 'Предпросмотр анкеты' : 'Сохранить черновик и предпросмотр', exact: true }).click();
      const previewReply = await previewResponse;
      expect(previewReply.status()).toBe(201);
      const previewPayload = await previewReply.json();
      save('preview-http', previewPayload);
      const preview = card.locator('.admin-questionnaire-preview');
      await expect(preview).toContainText('Готово к подтверждению');
      revisionId = Number(await preview.getAttribute('data-questionnaire-revision-id'));
      expect(revisionId).toBeGreaterThan(0);
      expect(previewPayload.id).toBe(revisionId);
      expect(previewPayload.assignment_ref).toBe('ADM28 isolated');
      expect(previewPayload.channel).toBe(channel);
      const previewDb = readDb(revisionId);
      save('preview-database', previewDb);
      expect(previewDb.revision.id).toBe(revisionId);
      expect(previewDb.revision.status).toBe('ready_for_confirmation');
      const confirmResponse = page.waitForResponse((response) => response.request().method() === 'POST'
        && response.url().endsWith(`/questionnaire/${revisionId}/confirm`));
      await preview.getByRole('button', { name: 'Подтвердить сведения', exact: true }).click();
      const confirmedReply = await confirmResponse;
      expect(confirmedReply.status()).toBe(200);
      save('confirm-http', await confirmedReply.json());
      await expect(card.locator('.admin-questionnaire-confirmation')).toContainText('Сведения подтверждены');
      const response = await page.request.get(`${base}/users/admin/organizations/${organizationId}/questionnaire/${revisionId}`);
      expect(response.status()).toBe(200);
      const saved = await response.json();
      save('http-readback', saved);
      expect(saved.id).toBe(revisionId);
      expect(saved.status).toBe('confirmed');
      expect(saved.assignment_ref).toBe('ADM28 isolated');
      expect(saved.channel).toBe(channel);
      expect(saved.source_author).toBe(sourceAuthor);
      expect(saved.answers_json.C01.name).toBe(channel === 'csv' ? 'Синтетическая организация' : fixture.fields.organization_name);
      const db = readDb(revisionId);
      save('database-readback', db);
      expect(db.owner_verified).toBe(true);
      expect(db.read_only_rollback).toBe(true);
      expect(db.revision.status).toBe('confirmed');
      expect(db.revision.source_author).toBe(sourceAuthor);
      expect(db.revision.assignment_ref).toBe(saved.assignment_ref);
      expect(db.revision.answers_json).toEqual(saved.answers_json);
      for (const name of unchangedCounts) expect(db.counts[name], `${name}: unchanged since synthetic seed`).toBe(baseline.counts[name]);
      expect(db.counts.questionnaire_revisions).toBe(baseline.counts.questionnaire_revisions + 1);
      await page.screenshot({ path: path.join(directory, 'confirmed-1440.png'), fullPage: true });
      await page.reload();
      await expect(card).toBeVisible();
      await card.locator(`.admin-organization-step[data-view="${channel === 'csv' ? 'questionnaire' : 'organization-data'}"]`).click();
      await expect(form.locator('[name="source_author"]')).toHaveValue(sourceAuthor);
      if (channel === 'product_form') {
        for (const [name, value] of Object.entries(fixture.fields)) await expect(form.locator(`[name="${name}"]`)).toHaveValue(value);
      }
      await expect(card.locator('.admin-questionnaire-confirmation')).toContainText('Сведения подтверждены');
      const listResponse = await page.request.get(`${base}/users/admin/organizations/${organizationId}/questionnaire`);
      expect(listResponse.status()).toBe(200);
      const list = await listResponse.json();
      save('revision-list-after-reload', list);
      expect(list.items.some((item) => item.id === revisionId && item.status === 'confirmed'
        && item.assignment_ref === 'ADM28 isolated')).toBe(true);
      expect(requests.filter((item) => item.method !== 'GET'
        && /\/(?:prepare|start|turns|control|continue)$/.test(item.path))).toEqual([]);
      save('result', { status: 'PASS', scope: 'local_synthetic_questionnaire_only', channel,
        revision_id: revisionId, actual_http: true, actual_postgresql: true,
        preview_status: 201, confirm_status: 200, exact_revision_readback: true,
        reload_readback: true, tested_actions_replaced_with_sql: false,
        provider_operations: 0, full_path_run: false, exec_run: false,
        report_run: false, requests, responses });
    } catch (error) {
      failure = error;
      save('failure', { status: 'FAIL', channel, error: error.message, revision_id: revisionId, requests, responses });
    } finally {
      // Persist independent read-only DB evidence BEFORE ownership-guarded DROP.
      if (created) {
        try { save('before-cleanup-readback', readDb(revisionId)); }
        catch (error) { save('before-cleanup-readback-error', { error: error.message }); failure ||= error; }
      }
      if (server && server.exitCode === null && server.signalCode === null) {
        const exited = new Promise((resolve) => server.once('exit', resolve));
        server.kill('SIGTERM');
        await Promise.race([exited, new Promise((resolve) => setTimeout(resolve, 5000))]);
        if (server.exitCode === null && server.signalCode === null) { server.kill('SIGKILL'); await exited; }
      }
      if (created) {
        try {
          cli('destroy');
          const cleanup = JSON.parse(fs.readFileSync(path.join(directory, 'cleanup.json'), 'utf8'));
          expect(cleanup.owner_verified).toBe(true);
          expect(cleanup.database_absent).toBe(true);
          expect(cleanup.state_absent).toBe(true);
          files['cleanup.json'] = createHash('sha256').update(fs.readFileSync(path.join(directory, 'cleanup.json'))).digest('hex');
        } catch (error) { save('cleanup-error', { error: error.message }); failure ||= error; }
      }
      save('evidence-manifest', { status: failure ? 'FAIL' : 'PASS', channel, files,
        excludes: ['state.json (ephemeral credentials; removed by owner cleanup)'] });
      await info.attach('questionnaire-evidence-manifest', {
        path: path.join(directory, 'evidence-manifest.json'), contentType: 'application/json',
      });
    }
    if (failure) throw failure;
  });
}
