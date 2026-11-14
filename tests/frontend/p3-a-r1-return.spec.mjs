import { test, expect } from '@playwright/test';
import { spawn, spawnSync } from 'node:child_process';
import { createHash, randomUUID } from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';

const root = process.cwd(), python = process.env.BROWSER_PYTHON || path.join(root, '.venv/bin/python');
const directory = path.join(root, '.test-stand/p3-a-r1', randomUUID());
const statePath = path.join(directory, 'state.json');
const evidence = process.env.P3_A_R1_EVIDENCE || path.join(process.env.P3_A_EVIDENCE || directory, 'r1-return');
let server, state, base;
function cli(action) {
  const result = spawnSync(python, ['scripts/p3-a-preview.py', action, '--state', statePath,
    '--port', '18935', '--return-profile', 'r1'], { cwd: root, encoding: 'utf8' });
  fs.appendFileSync(path.join(directory, 'prepare.log'), result.stdout + result.stderr);
  if (result.status !== 0) throw new Error(`R1 ${action}: ${result.stderr}`);
  return result.stdout;
}
test.beforeAll(async () => {
  if (!process.env.STAND_ADMIN_URL) throw new Error('Explicit owned localhost STAND_ADMIN_URL required');
  fs.mkdirSync(directory, { recursive: true }); fs.mkdirSync(evidence, { recursive: true });
  cli('create'); state = JSON.parse(fs.readFileSync(statePath)); base = `http://127.0.0.1:${state.port}`;
  const log = fs.openSync(path.join(directory, 'app.log'), 'a');
  server = spawn(python, ['scripts/p3-a-preview.py', 'serve', '--state', statePath],
    { cwd: root, stdio: ['ignore', log, log] }); fs.closeSync(log);
  await expect.poll(async () => { try { return (await fetch(`${base}/health/ready`)).status; } catch { return 0; } },
    { timeout: 30000 }).toBe(200);
  const identity = await (await fetch(`${base}/p3-a/identity`)).json();
  expect(identity.run_id).toBe(state.run_id); expect(identity.return_profile).toBe('r1');
  for (const [file, hash] of Object.entries(identity.startup_fingerprints)) {
    expect(createHash('sha256').update(fs.readFileSync(path.join(root, file))).digest('hex'), file).toBe(hash);
  }
  fs.writeFileSync(path.join(evidence, 'source-identity.json'), JSON.stringify(identity, null, 2) + '\n');
});
test.afterAll(async () => {
  try {
    if (state && fs.existsSync(statePath)) fs.writeFileSync(path.join(evidence, 'pg-readback.json'), cli('inspect'));
  } finally {
    if (server && server.exitCode === null) {
      const ended = new Promise((resolve) => server.once('exit', resolve)); server.kill('SIGTERM');
      await Promise.race([ended, new Promise((resolve) => setTimeout(resolve, 5000))]);
      if (server.exitCode === null) { server.kill('SIGKILL'); await ended; }
    }
    if (fs.existsSync(statePath)) { cli('destroy'); fs.copyFileSync(path.join(directory, 'cleanup.json'), path.join(evidence, 'cleanup.json')); }
  }
});

test.beforeEach(async ({ page }) => {
  page.r1Diagnostics = [];
  page.on('response', async (response) => {
    const pathname = new URL(response.url()).pathname;
    if (!pathname.startsWith('/users/assessment/')) return;
    try {
      const body = await response.json();
      page.r1Diagnostics.push({ pathname, method: response.request().method(), status: response.status(),
        detail: body.detail, collection_status: body.status?.collection_status,
        assessment_situation_id: body.current_situation?.assessment_situation_id,
        situation_status: body.current_situation?.status, allowed_action: body.allowed_action });
    } catch { /* A navigation may discard a completed body. */ }
  });
});
test.afterEach(async ({ page }) => {
  fs.writeFileSync(path.join(evidence, 'assessment-http-diagnostics.json'), JSON.stringify(page.r1Diagnostics, null, 2) + '\n');
  fs.writeFileSync(path.join(evidence, 'delivery-ui-diagnostics.json'), JSON.stringify({
    error: await page.locator('#interview-error').textContent().catch(() => 'page_closed'),
    submit_label: await page.locator('#interview-submit-button').textContent().catch(() => 'page_closed'),
    pending_labels: await page.locator('.interview-message-delivery-status').allTextContents().catch(() => []),
  }, null, 2) + '\n');
});

test('P3-AC01/03 initial runtime withheld over real HTTP keeps input disabled until the AS is presented', async ({ page }) => {
  const target = state.p3_a_previews.long;
  const pathname = `/users/assessment/cycles/${target.cycle_id}/runtime`;
  let intercepted = false, release;
  const gate = new Promise((resolve) => { release = resolve; });
  await page.route('**' + pathname, async (route) => {
    if (!intercepted && route.request().method() === 'GET') {
      intercepted = true; await gate;
    }
    return route.continue();
  });
  try {
    await page.goto(`${base}/p3-a/open/long`);
    await expect.poll(() => intercepted).toBe(true);
    const input = page.locator('#interview-textarea'), submit = page.locator('#interview-submit-button');
    await expect(input).toBeDisabled(); await expect(submit).toBeDisabled();
    await expect(page.locator('#interview-finish-button')).toBeDisabled();
    await expect(page.locator('.interview-message--situation')).toHaveCount(0);
    await page.screenshot({ path: path.join(evidence, 'startup-runtime-held.png'), fullPage: false });
    release();
    await expect(page.locator('.interview-message--situation')).toHaveCount(1);
    await expect(input).toBeEnabled(); await expect(submit).toBeEnabled();
    const answer = 'Синтетический ответ сразу после подтверждения готовности runtime.';
    await input.fill(answer);
    const sent = page.waitForResponse((response) => /\/m5\/situations\/[^/]+\/turns$/.test(new URL(response.url()).pathname)
      && response.request().method() === 'POST', { timeout: 15000 });
    await submit.click(); expect((await sent).ok()).toBe(true);
    await expect(page.locator('.interview-message.own').filter({ hasText: answer })).toHaveCount(1);
    const model = await (await page.request.get(`${base}${pathname}`)).json();
    expect(model.trace.turns.filter((turn) => turn.content_text === answer)).toHaveLength(1);
    fs.writeFileSync(path.join(evidence, 'startup-runtime-readiness.json'), JSON.stringify({
      transport: 'initial runtime GET held then continued; no response body mock',
      input_disabled_until_runtime: true, send_disabled_until_runtime: true,
      finish_disabled_until_runtime: true, presented_situations: 1,
      immediate_post_after_readiness: 200, saved_turns: 1,
    }, null, 2) + '\n');
  } finally { release(); await page.unroute('**' + pathname); }
});

test('P3-AC10 R1 v2 initial snapshot: explicit Continue keeps AS, saved Turn and unsent draft without replacement', async ({ page }, info) => {
  info.annotations.push({ type: 'scope', description:
    'New owned assessment-scope synthetic fixture; published R1v2 initially snapshotted. Expired presence lease is synthetic upstream input; NOT physical absence, pilot admission or AC18 PATH. Real auth/runtime/return-continue/PG.' });
  const target = state.p3_a_previews.long;
  await page.goto(`${base}/p3-a/open/long`);
  await expect(page.locator('.interview-message--situation')).toHaveCount(1);
  const input = page.locator('#interview-textarea'); await expect(input).toBeEnabled();
  const answer = 'Синтетический сохранённый ответ перед возвратом R1.';
  await input.fill(answer);
  const submitted = page.waitForResponse((response) => /\/m5\/situations\/[^/]+\/turns$/.test(new URL(response.url()).pathname)
    && response.request().method() === 'POST', { timeout: 15000 });
  await page.locator('#interview-submit-button').click(); expect((await submitted).ok()).toBe(true);
  await expect(page.locator('.interview-message.own').filter({ hasText: answer })).toHaveCount(1);
  const draft = 'Непринятый многострочный черновик R1\nУсловия и следующий шаг.';
  await input.fill(draft);
  await page.goto(`${base}/p3-a/open/continue`);
  await expect(page.locator('.interview-return-card')).toBeVisible();
  await expect(input).toBeDisabled();
  await expect(page.locator('.interview-message--situation')).toHaveCount(0);
  const prefix = `${base}/users/assessment/m7/cycles/${target.cycle_id}`;
  const before = await (await page.request.get(prefix + '/return-state')).json();
  expect(before.allowed_action).toBe('continue_current');
  expect(before.current_assessment_situation_id).toBe(target.assessment_situation_id);
  expect(before.policy_ref).toEqual({ id: 'sales-pilot-return-r1', version: '2.0',
    checksum: '1121db8c84b6997ee427264a589b5db088588e134734d8ae0dbc0d2220a36f14' });
  const blocked = await page.request.get(`${base}/users/assessment/cycles/${target.cycle_id}/runtime`);
  expect([404, 409]).toContain(blocked.status());
  await page.screenshot({ path: path.join(evidence, 'explicit-return-card.png'), fullPage: false });
  const continued = page.waitForResponse((response) => new URL(response.url()).pathname.endsWith('/return-continue')
    && response.request().method() === 'POST');
  await page.locator('.interview-return-card').getByRole('button', { name: 'Продолжить', exact: true }).click();
  const response = await continued; expect(response.ok()).toBe(true);
  const result = await response.json(); expect(result.branch).toBe('continued_current');
  expect(result.assessment_situation_id).toBe(target.assessment_situation_id);
  await expect(input).toBeEnabled(); await expect(input).toHaveValue(draft);
  await expect(page.locator('.interview-message--situation')).toHaveCount(1);
  await expect(page.locator('.interview-message.own').filter({ hasText: answer })).toHaveCount(1);
  const runtime = await (await page.request.get(`${base}/users/assessment/cycles/${target.cycle_id}/runtime`)).json();
  expect(runtime.current_situation.assessment_situation_id).toBe(target.assessment_situation_id);
  expect(runtime.trace.turns.filter((turn) => turn.content_text === answer)).toHaveLength(1);
  expect(runtime.trace.turns.filter((turn) => turn.content_text === draft)).toHaveLength(0);
  expect(runtime.route.positions.flatMap((position) => position.history).filter((row) => row.disposition === 'replaced')).toHaveLength(0);
  await page.reload(); await expect(input).toHaveValue(draft);
  await expect(page.locator('.interview-message.own').filter({ hasText: answer })).toHaveCount(1);
  fs.writeFileSync(path.join(evidence, 'return-http-readback.json'), JSON.stringify({ before,
    blocked_runtime_status: blocked.status(), continued: result,
    same_assessment_situation: runtime.current_situation.assessment_situation_id,
    persisted_answer_count: 1, draft_not_a_turn: true, replacements: 0 }, null, 2) + '\n');
  await page.screenshot({ path: path.join(evidence, 'same-as-draft-and-history-after-continue.png'), fullPage: false });
});

test('REMAIN06 lost Continue response: same command readback, two tabs and foreign scope', async ({ page, context }) => {
  const target = state.p3_a_previews.long;
  await page.goto(`${base}/p3-a/open/continue`);
  await expect(page.locator('.interview-return-card')).toBeVisible();
  const second = await context.newPage();
  try {
    await second.goto(`${base}/?screen=interview&cycle_id=${target.cycle_id}`);
    await expect(second.locator('.interview-return-card')).toBeVisible();
    const command = `/users/assessment/m7/cycles/${target.cycle_id}/return-continue`;
    let accepted, body, posts = 0;
    await page.route('**' + command, async (route) => {
      posts++; body = route.request().postDataJSON();
      const response = await route.fetch({ timeout: 15000, maxRetries: 0 });
      expect(response.status()).toBe(200); accepted = await response.json();
      await route.abort('failed'); // Server commit happened; browser did not receive it.
    });
    await page.locator('.interview-return-card').getByRole('button', { name: 'Продолжить', exact: true }).click();
    await expect(page.locator('.interview-message--situation')).toHaveCount(1);
    expect(posts).toBe(1);
    expect(accepted.assessment_situation_id).toBe(target.assessment_situation_id);
    const replay = await page.request.post(base + command, { data: body, timeout: 15000 });
    expect(replay.status()).toBe(200); expect(await replay.json()).toEqual(accepted);
    await second.reload();
    await expect(second.locator('.interview-message--situation')).toHaveCount(1);
    const runtime = await (await second.request.get(`${base}/users/assessment/cycles/${target.cycle_id}/runtime`)).json();
    expect(runtime.current_situation.assessment_situation_id).toBe(target.assessment_situation_id);
    expect(runtime.route.positions.flatMap((p) => p.history).filter((h) => h.disposition === 'replaced')).toHaveLength(0);
    const foreign = await page.request.post(`${base}/users/assessment/m7/cycles/${state.p3_a_previews.short.cycle_id}/return-continue`,
      { data: body, timeout: 15000 });
    expect(foreign.status()).toBe(403);
    fs.writeFileSync(path.join(evidence, 'remain06-lost-continue.json'), JSON.stringify({
      cycle_id: target.cycle_id, assessment_situation_id: target.assessment_situation_id,
      posted_commands: posts, command_key: body.idempotency_key, readback_same_as: true,
      replay_same_receipt: true, two_tabs_same_as: true, foreign_status: foreign.status(),
    }, null, 2) + '\n');
  } finally { await second.close(); }
});
