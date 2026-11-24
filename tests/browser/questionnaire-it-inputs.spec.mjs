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
    const readDb = (id = 0) => JSON.parse(run('tests/questionnaire_it_readback.py',
      ['--state', statePath, '--revision-id', String(id)]));
    const baseline = readDb();
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
    await expect(card.locator('.admin-questionnaire-load-state').filter({ hasText: 'Загружаем' })).toHaveCount(0);
    const form = card.locator('[data-action="preview-early-data"]');
    await expect(form.locator('[name="assignment_ref"]')).toHaveValue('ADM28 isolated');
    const nameField = form.getByRole('textbox', { name: 'Название организации', exact: true });
    const originalName = 'Синтетическая организация ADM28';
    await expect(nameField).toBeEditable();
    await expect(nameField).toHaveValue(originalName);
    const storedOrganizationName = async () => {
      const response = await page.request.get(base + '/users/admin/organizations');
      expect(response.status()).toBe(200);
      return (await response.json()).items.find((item) => String(item.id) === organizationId)?.name;
    };
    for (const [name, value] of Object.entries(values)) {
      if (!['source_author', 'organizer'].includes(name)) {
        const field = form.locator(`[name="${name}"]`);
        if (['case_reality_level', 'organization_name_usage_rules'].includes(name)) await field.selectOption(value);
        else await field.fill(value);
      }
    }
    const assertValues = async () => {
      for (const [name, value] of Object.entries(values)) {
        if (!['source_author', 'organizer'].includes(name)) await expect(form.locator(`[name="${name}"]`)).toHaveValue(value);
      }
    };
    await assertValues();
    await capturePathViewports(page, directory, 'it-questionnaire', [
      { name: 'purpose', locator: form.locator('[name="purpose"]') },
      { name: 'organization-name', locator: form.locator('[name="organization_name"]') },
      { name: 'organization-type', locator: form.locator('[name="organization_type"]') },
      { name: 'preview', locator: form.getByRole('button', { name: 'Подтвердить сведения', exact: true }) },
    ]);
    await assertValues();
    save('filled-fields', { values, all_10_fields_retained: true, viewport_widths: [1440, 320, 390, 768] });
    const questionnairePath = `/users/admin/organizations/${organizationId}/questionnaire`;
    const previewURL = base + questionnairePath + '/preview';
    const preview = card.locator('.admin-questionnaire-preview');
    const revisionId = await test.step('Вернуть исходный черновик после потери ответа и перезагрузки', async () => {
      let firstPreview, firstKey;
      await page.route(previewURL, async (route) => {
        firstKey = route.request().postDataJSON().idempotency_key;
        const committed = await route.fetch();
        expect(committed.status()).toBe(201);
        firstPreview = await committed.json();
        await route.abort('connectionreset');
      }, { times: 1 });
      await form.locator('[data-early-data-submit]').click();
      await expect(form.locator('[data-operation-status]')).toContainText('Не удалось получить ответ');
      expect(firstKey).toBeTruthy();
      expect(firstPreview.status).toBe('ready_for_confirmation');
      const afterWrite = readDb(firstPreview.id);
      expect(afterWrite.revision.status).toBe('ready_for_confirmation');
      expect(afterWrite.counts.questionnaire_revisions).toBe(baseline.counts.questionnaire_revisions + 1);
      expect(afterWrite.counts.organization_context_versions).toBe(baseline.counts.organization_context_versions);

      await page.reload();
      await assertValues();
      const replayed = page.waitForResponse((response) => response.request().method() === 'POST' && response.url() === previewURL);
      await form.locator('[data-early-data-submit]').press('Enter');
      const replay = await replayed;
      expect(replay.status()).toBe(201);
      expect(replay.request().postDataJSON().idempotency_key).toBe(firstKey);
      expect((await replay.json()).id).toBe(firstPreview.id);
      await expect(preview.getByRole('button', { name: 'Подтвердить сведения', exact: true })).toBeEnabled();
      await expect(preview.locator('[data-organization-rename]')).toContainText(`с «${originalName}» на «${values.organization_name}»`);
      expect(await storedOrganizationName()).toBe(originalName);
      expect(await preview.getAttribute('data-questionnaire-revision-id')).toBe(String(firstPreview.id));
      const afterReload = readDb(firstPreview.id);
      expect(afterReload.counts).toEqual(afterWrite.counts);
      save('preview-after-reload', {
        revision_id: firstPreview.id, same_idempotency_key: true,
        counts_after_write: afterWrite.counts, counts_after_replay: afterReload.counts,
      });
      return String(firstPreview.id);
    });
    if (process.env.P4K_F05_DRAFT_ONLY === '1') {
      await page.reload();
      await card.getByRole('button', { name: 'Участники оценки', exact: true }).click();
      await expect(card.locator('form[data-action="assign-member-assessment"]')).toHaveCount(0);
      await card.getByRole('button', { name: 'Данные организации', exact: true }).click();
      const readiness = card.locator('.admin-data-readiness');
      await expect(readiness).toContainText('не подтверждена');
      const draft = JSON.parse(run('tests/questionnaire_it_readback.py', ['--state', statePath,
        '--revision-id', revisionId]));
      expect(draft.revision.status).not.toBe('confirmed');
      expect(draft.counts.questionnaire_revisions).toBe(baseline.counts.questionnaire_revisions + 1);
      expect(draft.counts.assignments).toBe(baseline.counts.assignments);
      save('f05-draft-only', { revision_id: Number(revisionId), revision_status: draft.revision.status,
        assignment_status: await readiness.locator('dt:text-is("Анкета") + dd').textContent(), revision_count: draft.counts.questionnaire_revisions,
        assignment_count: draft.counts.assignments, baseline_assignment_count: baseline.counts.assignments });
      return;
    }
    await test.step('После потери ответа подтверждения прочитать точный ID без второго POST', async () => {
      const revisionPath = questionnairePath + '/' + revisionId;
      const confirmURL = base + revisionPath + '/confirm';
      await page.route(confirmURL, async (route) => {
        const committed = await route.fetch();
        expect(committed.status()).toBe(200);
        await route.abort('connectionreset');
      }, { times: 1 });
      await preview.getByRole('button', { name: 'Подтвердить сведения', exact: true }).click();
      await expect(card.locator('.admin-data-confirmation-recovery')).toContainText('Итог подтверждения неизвестен');
      const afterWrite = readDb(revisionId);
      expect(afterWrite.revision.status).toBe('confirmed');
      expect(afterWrite.revision.organization_context_version_id).toBeGreaterThan(0);
      expect(afterWrite.counts.questionnaire_revisions).toBe(baseline.counts.questionnaire_revisions + 1);
      expect(afterWrite.counts.organization_context_versions).toBe(baseline.counts.organization_context_versions + 1);

      const beforeReload = requests.length;
      const readback = page.waitForResponse((response) => response.request().method() === 'GET' &&
        response.url() === base + revisionPath);
      await page.reload();
      const read = await readback;
      expect(read.status()).toBe(200);
      expect(await read.json()).toMatchObject({
        id: Number(revisionId), assignment_ref: 'ADM28 isolated', status: 'confirmed',
      });
      await expect(card.locator('[data-organization-confirmed]')).toBeVisible();
      await expect(card.locator('.admin-data-confirmed-icon')).toHaveText('✓');
      await expect(form.locator('[data-early-data-submit]')).toBeHidden();
      expect(await storedOrganizationName()).toBe(values.organization_name);
      const recoveryRequests = requests.slice(beforeReload).filter((request) => request.path.startsWith(questionnairePath));
      expect(recoveryRequests[0]).toEqual({ method: 'GET', path: revisionPath });
      expect(recoveryRequests.every((request) => request.method === 'GET')).toBe(true);
      expect(requests.filter((request) => request.path === revisionPath + '/confirm')).toHaveLength(1);
      const afterReload = readDb(revisionId);
      expect(afterReload.revision.organization_context_version_id).toBe(afterWrite.revision.organization_context_version_id);
      expect(afterReload.counts).toEqual(afterWrite.counts);
      save('confirmation-after-reload', {
        revision_id: Number(revisionId), context_version_id: afterWrite.revision.organization_context_version_id,
        confirm_posts: 1, recovered_by: recoveryRequests[0],
        counts_after_write: afterWrite.counts, counts_after_reload: afterReload.counts,
      });
    });
    const getRevision = () => page.request.get(`${base}/users/admin/organizations/${organizationId}/questionnaire/${revisionId}`);
    const response = await getRevision();
    expect(response.status()).toBe(200);
    const saved = await response.json();
    save('http-readback', saved);
    expect(saved.status).toBe('confirmed');
    expect(saved.source_author).toBe('');
    expect(saved.uploaded_by_user_id).toBeGreaterThan(0);
    expect(saved.answers_json.C01.name).toBe(values.organization_name);
    expect(saved.answers_json.C01.organization_type).toBe(values.organization_type);
    await page.screenshot({ path: path.join(directory, 'confirmed-1440.png'), fullPage: true });
    await page.reload();
    await expect(form.locator('[name="source_author"]')).toHaveCount(0);
    await assertValues();
    const db = JSON.parse(run('tests/questionnaire_it_readback.py', ['--state', statePath, '--revision-id', revisionId]));
    save('database-readback', db);
    expect(db.revision.status).toBe('confirmed');
    expect(db.revision.source_author).toBe('');
    expect(db.revision.answers_json).toEqual(saved.answers_json);
    for (const name of ['assignments', 'profiles', 'preparation_operations', 'cycles', 'assessment_situations', 'assessment_answers']) {
      expect(db.counts[name], `${name}: unchanged since synthetic seed`).toBe(baseline.counts[name]);
    }
    expect(db.counts.questionnaire_revisions).toBe(baseline.counts.questionnaire_revisions + 1);
    if (process.env.P4K_F05_INCOMPLETE_LATE_SAVE === '1') {
      const incompleteName = values.organization_name + ' — неполный черновик';
      await form.locator('[name="organization_name"]').fill(incompleteName);
      await form.locator('[name="purpose"]').fill('');
      let releaseResponse, committedResponse;
      const releaseGate = new Promise((resolve) => { releaseResponse = resolve; });
      const committedGate = new Promise((resolve) => { committedResponse = resolve; });
      const previewPath = `**/users/admin/organizations/${organizationId}/questionnaire/preview`;
      let previewPosts = 0;
      await page.route(previewPath, async (route) => {
        if (route.request().method() !== 'POST') return route.continue();
        previewPosts += 1;
        const committed = await route.fetch();
        expect(committed.status()).toBe(201);
        committedResponse();
        await releaseGate;
        await route.fulfill({ response: committed });
      });
      try {
        await form.getByRole('button', { name: 'Подтвердить сведения', exact: true }).click();
        await committedGate;
        await page.locator('#admin-organizations-account-name').click();
  await page.locator('#admin-organizations-logout-button').click();
        await expect(page.locator('#email-input')).toBeVisible();
        await page.locator('#email-input').fill('admin@example.test');
        await page.locator('#request-magic-link-button').click();
        await page.locator('#magic-token-input').fill(state.password);
        await page.locator('#verify-magic-link-button').click();
        await expect(page.locator('#admin-organizations-panel')).toBeVisible();
        releaseResponse();
        await page.waitForTimeout(500);
        await card.getByRole('button', { name: 'Данные организации', exact: true }).click();
        await expect(card.locator('.admin-data-readiness')).toContainText(
          `действует подтверждённая редакция #${revisionId}; новый черновик ещё не подтверждён`);
        const revisions = await (await page.request.get(
          `${base}/users/admin/organizations/${organizationId}/questionnaire`)).json();
        const latest = revisions.items.find((item) => item.assignment_ref === saved.assignment_ref);
        expect(latest.status).not.toBe('confirmed');
        expect(latest.effective_confirmed.id).toBe(Number(revisionId));
        const draft = JSON.parse(run('tests/questionnaire_it_readback.py', ['--state', statePath,
          '--revision-id', String(latest.id)]));
        expect(draft.counts.questionnaire_revisions).toBe(baseline.counts.questionnaire_revisions + 2);
        expect(draft.counts.assignments).toBe(baseline.counts.assignments);
        save('f05-incomplete-late-save', { confirmed_revision_id: Number(revisionId),
          draft_revision_id: latest.id, draft_status: latest.status,
          effective_confirmed_revision_id: latest.effective_confirmed.id,
          delayed_preview_posts: previewPosts, assignment_count: draft.counts.assignments });
        return;
      } finally {
        releaseResponse();
        await page.unroute(previewPath);
      }
    }
    const draftName = values.organization_name + ' — черновик';
    await nameField.fill(draftName);
    await expect(form.locator('[data-organization-confirmed]')).toBeHidden();
    await expect(card.locator('[data-preview-value="organization_name"]')).toHaveText(draftName);
    const draftResponse = page.waitForResponse((response) => response.request().method() === 'POST'
      && response.url().endsWith(`/users/admin/organizations/${organizationId}/questionnaire/preview`));
    await form.getByRole('button', { name: 'Подтвердить сведения', exact: true }).click();
    expect((await draftResponse).status()).toBe(201);
    const draftList = await page.request.get(`${base}/users/admin/organizations/${organizationId}/questionnaire`);
    expect(draftList.status()).toBe(200);
    const latest = (await draftList.json()).items.find((item) => item.assignment_ref === saved.assignment_ref);
    expect(latest.status).not.toBe('confirmed');
    expect(latest.effective_confirmed.id).toBe(Number(revisionId));
    if (process.env.P4K_F05_CONFIRM_LOST === '1') {
      const confirmPath = `**/users/admin/organizations/${organizationId}/questionnaire/${latest.id}/confirm`;
      let confirmPosts = 0;
      await page.route(confirmPath, async (route) => {
        confirmPosts += 1;
        const committed = await route.fetch();
        expect(committed.status()).toBe(200);
        await route.abort('failed');
      });
      await card.locator('.admin-questionnaire-preview').getByRole('button',
        { name: 'Подтвердить сведения', exact: true }).click();
      await expect(card).toContainText('Итог подтверждения неизвестен');
      expect(confirmPosts).toBe(1);
      await page.unroute(confirmPath);
      const readback = page.waitForResponse((r) => r.request().method() === 'GET' &&
        r.url().endsWith('/questionnaire/' + latest.id));
      await card.getByRole('button', { name: 'Проверить результат' }).press('Enter');
      expect((await readback).status()).toBe(200);
      await expect(form.locator('[data-organization-confirmed]')).toBeVisible();
      const afterCommit = await (await page.request.get(
        `${base}/users/admin/organizations/${organizationId}/questionnaire`)).json();
      const effective = afterCommit.items.find((item) => item.assignment_ref === saved.assignment_ref);
      expect(effective.id).toBe(latest.id);
      expect(effective.status).toBe('confirmed');
      expect(effective.effective_confirmed.id).toBe(latest.id);
      const original = await (await page.request.get(
        `${base}/users/admin/organizations/${organizationId}/questionnaire/${revisionId}`)).json();
      expect(original.status).toBe('confirmed');
      await page.reload();
      await card.getByRole('button', { name: 'Данные организации', exact: true }).click();
      await expect(card.locator('.admin-data-readiness dt:text-is("Анкета") + dd')).toHaveText('подтверждена');
      const confirmedDb = JSON.parse(run('tests/questionnaire_it_readback.py', ['--state', statePath,
        '--revision-id', String(latest.id)]));
      expect(confirmedDb.revision.status).toBe('confirmed');
      expect(confirmedDb.counts.questionnaire_revisions).toBe(baseline.counts.questionnaire_revisions + 2);
      save('f05-confirm-lost-response', { confirmed_revision_id: Number(revisionId),
        newly_confirmed_revision_id: latest.id, confirm_posts: confirmPosts,
        original_status: original.status, effective_confirmed_revision_id: effective.effective_confirmed.id,
        database_revision_status: confirmedDb.revision.status,
        database_revision_count: confirmedDb.counts.questionnaire_revisions,
        baseline_revision_count: baseline.counts.questionnaire_revisions });
      return;
    }
    await page.reload();
    await expect(form.locator('[name="organization_name"]')).toHaveValue(draftName);
    await expect(card.locator('.admin-data-readiness')).toContainText(
      `действует подтверждённая редакция #${revisionId}; новый черновик ещё не подтверждён`);
    await card.locator('.admin-data-readiness summary').click();
    for (const [name, width, zoom] of [
      ['desktop-1440', 1440, 1], ['mobile-390', 390, 1],
      ['mobile-320', 320, 1], ['mobile-320-text-200', 320, 2],
    ]) {
      await page.setViewportSize({ width, height: 900 });
      await page.evaluate((scale) => { document.documentElement.style.zoom = String(scale); }, zoom);
      await expect(card.locator('.admin-data-readiness')).toBeVisible();
      await page.screenshot({ path: path.join(directory, `f05-confirmed-with-draft-${name}.png`), fullPage: true });
    }
    await page.evaluate(() => { document.documentElement.style.zoom = '1'; });
    const draftDb = JSON.parse(run('tests/questionnaire_it_readback.py', ['--state', statePath,
      '--revision-id', String(latest.id)]));
    expect(draftDb.revision.status).not.toBe('confirmed');
    expect(draftDb.counts.questionnaire_revisions).toBe(baseline.counts.questionnaire_revisions + 2);
    save('confirmed-with-new-draft', { confirmed_revision_id: Number(revisionId), draft_revision_id: latest.id,
      http: latest, database: draftDb });
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
