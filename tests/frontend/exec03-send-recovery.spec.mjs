// EXEC03 real HTTP/owned PostgreSQL regression. No shared fixtures are changed.
// Existing scripts/p3-a-preview.py server + marker-owned PostgreSQL are required.
import { createRequire } from 'node:module';
import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { createHash, randomUUID } from 'node:crypto';
const require = createRequire(path.join(process.cwd(), 'package.json'));
const { test, expect } = require('@playwright/test');
const root = process.cwd();
const statePath = process.env.EXEC03_STATE;
if (!statePath || !process.env.STAND_ADMIN_URL) throw new Error('EXEC03_STATE and isolated STAND_ADMIN_URL required');
const state = JSON.parse(fs.readFileSync(statePath, 'utf8'));
const base = `http://127.0.0.1:${state.port}`;
const target = state.p3_a_previews.long;
const asId = target.assessment_situation_id;
const cycleId = target.cycle_id;
const turnsPath = `/users/assessment/m5/situations/${asId}/turns`;
const runtimePath = `/users/assessment/cycles/${cycleId}/runtime`;
const fixture = JSON.parse(fs.readFileSync(path.join(root, 'tests/browser/fixtures/v1.json'), 'utf8'));
const python = process.env.BROWSER_PYTHON || path.join(root, '.venv/bin/python');
const readbackScript = process.env.EXEC03_READBACK_SCRIPT || path.join(import.meta.dirname, 'exec03_pg_readback.py');
const evidence = process.env.EXEC03_EVIDENCE || path.join(path.dirname(statePath), 'evidence');
fs.mkdirSync(evidence, { recursive: true });
test.describe.configure({ mode: 'serial' });
let ordinaryAcceptedBody, askAcceptedBody, askAcceptedEndpoint;

test.beforeAll(async () => {
  const response = await fetch(base + '/exec03/identity');
  expect(response.status).toBe(200);
  const identity = await response.json();
  expect(identity.fixture).toBe('exec03_r1_technical_gateway/1');
  expect(identity.run_id).toBe(state.run_id); expect(identity.provider_mode).toBe('disabled');
  const expected = process.env.EXEC03_EXPECTED_SHA || spawnSync('git', ['rev-parse', 'HEAD'], { cwd: root, encoding: 'utf8' }).stdout.trim();
  expect(identity.source_head_sha).toBe(expected);
  for (const [name, digest] of Object.entries(identity.startup_fingerprints)) {
    expect(createHash('sha256').update(fs.readFileSync(path.join(root, name))).digest('hex'), name).toBe(digest);
  }
  fs.writeFileSync(path.join(evidence, 'source-identity.json'), JSON.stringify(identity, null, 2) + '\n');
});

function pg(name, targetAsId = asId) {
  const run = spawnSync(python, [readbackScript, '--root', root, '--state', statePath, '--as-id', targetAsId],
    { cwd: root, env: process.env, encoding: 'utf8' });
  expect(run.status, run.stderr).toBe(0);
  const value = JSON.parse(run.stdout);
  fs.writeFileSync(path.join(evidence, `${name}.json`), JSON.stringify(value, null, 2) + '\n');
  return value;
}
async function runtime(page) {
  const response = await page.request.get(base + runtimePath);
  expect(response.status()).toBe(200);
  return response.json();
}
async function open(page) {
  page.on('dialog', (dialog) => dialog.accept());
  await page.goto(base + '/p3-a/open/long');
  await expect(page.locator('#interview-panel')).toBeVisible();
  await expect(page.locator('#interview-textarea')).toBeEnabled();
}
function pending(page) {
  return page.evaluate(() => Object.entries(sessionStorage)
    .filter(([key]) => key.startsWith('agent4k.assessmentPending:') && !key.includes(':resolved:'))
    .map(([key, value]) => ({ key, ...JSON.parse(value) })));
}
async function sameKey(page, endpoint, body, expected = 200) {
  const response = await page.request.post(base + endpoint, { data: body });
  expect(response.status(), `${endpoint}: expected ${expected}, received ${response.status()}`).toBe(expected);
  return response;
}
async function saveScreenshot(page, name) {
  await page.screenshot({ path: path.join(evidence, `${name}.png`), fullPage: true });
}
function assertNoExtraEffects(before, after) {
  expect(after.turns).toEqual(before.turns);
  expect(after.events).toEqual(before.events);
  expect(after.operations).toEqual(before.operations);
  expect(after.clarifications).toEqual(before.clarifications);
  expect(after.c45_handoffs).toEqual(before.c45_handoffs);
  expect(after.evidence_requests).toEqual(before.evidence_requests);
  expect(after.assessment_requests).toEqual(before.assessment_requests);
  expect(after.pipeline_revision_ids).toEqual(before.pipeline_revision_ids);
}

test('EXEC03 C1–C6 ordinary Turn: loss, stable identity, two reloads/tabs, replay/conflict/new identical text', async ({ page, context }) => {
  test.setTimeout(180000);
  await open(page);
  const input = page.locator('#interview-textarea');
  const submit = page.locator('#interview-submit-button');
  const draft = `Несохранённый черновик EXEC03 ${randomUUID()}`;
  await input.fill(draft); await page.reload();
  await expect(input).toHaveValue(draft);
  // C1 normal submit, then a deliberately new submit with identical text (C6).
  await submit.click(); await expect(input).toHaveValue(''); await expect(submit).toBeEnabled();
  const normal = pg('ordinary-normal');
  expect(normal.turns.filter((turn) => turn.content_text === draft)).toHaveLength(1);
  const normalTurn = normal.turns.find((turn) => turn.content_text === draft);
  ordinaryAcceptedBody = { request_id: normalTurn.request_id, turn_id: normalTurn.turn_id, content: normalTurn.content_text };
  await input.fill(draft); await submit.click();
  await expect(input).toHaveValue(''); await expect(submit).toBeEnabled();
  const repeated = pg('ordinary-deliberately-repeated-text');
  const equalTurns = repeated.turns.filter((turn) => turn.content_text === draft);
  expect(equalTurns).toHaveLength(2);
  expect(new Set(equalTurns.map((turn) => turn.request_id)).size).toBe(2);
  expect(new Set(equalTurns.map((turn) => turn.turn_id)).size).toBe(2);

  // Keep a real committed response in flight while a cloned tab restores it.
  // Delivery of that late original receipt must not create a second effect.
  const lateText = 'EXEC03 late response ' + randomUUID();
  let lateBody; let releaseLate; let committedLate;
  const lateGate = new Promise((resolve) => { releaseLate = resolve; });
  await page.route('**' + turnsPath, async (route) => {
    lateBody = route.request().postDataJSON();
    const response = await route.fetch(); expect(response.status()).toBe(200);
    committedLate = true;
    await lateGate;
    try { await route.fulfill({ response }); } catch { /* Closed transport never replays a write. */ }
  });
  await input.fill(lateText); await submit.click();
  await expect.poll(() => committedLate).toBe(true);
  const copiedLate = await page.evaluate(() => Object.entries(sessionStorage));
  const recoveryTab = await context.newPage();
  await recoveryTab.addInitScript((entries) => entries.forEach(([key, value]) => sessionStorage.setItem(key, value)), copiedLate);
  await recoveryTab.goto(page.url());
  await expect(recoveryTab.locator('#interview-submit-button')).toBeEnabled();
  await expect(recoveryTab.locator('#interview-textarea')).toHaveValue('');
  const beforeLate = pg('ordinary-late-response-before-replay');
  await Promise.all([sameKey(recoveryTab, turnsPath, lateBody), sameKey(recoveryTab, turnsPath, lateBody)]);
  await recoveryTab.locator('#interview-textarea').fill('Новый собственный ввод после readback');
  releaseLate();
  await expect(submit).toBeEnabled();
  await expect(recoveryTab.locator('#interview-textarea')).toHaveValue('Новый собственный ввод после readback');
  assertNoExtraEffects(beforeLate, pg('ordinary-late-response-after-replay'));
  await recoveryTab.close(); await page.unroute('**' + turnsPath);

  for (const accepted of [true, false]) {
    const text = `EXEC03 ${accepted ? 'после commit' : 'до сервера'} ${randomUUID()}`;
    const requests = []; let first = true; let operation;
    await page.route('**' + turnsPath, async (route) => {
      requests.push(route.request().postDataJSON());
      if (!first) return route.continue();
      first = false;
      operation = (await pending(page)).find((item) => item.requestId === requests[0].request_id);
      if (accepted) {
        const committed = await route.fetch();
        expect(committed.status()).toBe(200); // Actual HTTP/PG commit.
      }
      return route.abort('failed'); // Never fake a successful response.
    });
    await input.fill(text); await submit.click();
    await expect.poll(() => requests.length).toBe(1);
    await expect(page.locator('#interview-error')).toBeVisible();
    expect(operation).toBeTruthy();
    expect(operation.requestId).toBe(requests[0].request_id);
    expect(operation.turnId).toBe(requests[0].turn_id);
    expect(operation.endpoint).toBe(turnsPath);
    for (let n = 0; n < 2; n += 1) {
      await page.reload(); await expect(page.locator('#interview-panel')).toBeVisible();
      await expect(page.locator('.interview-message.own').filter({ hasText: text })).toHaveCount(1);
      await expect(input).toHaveValue(accepted ? '' : text);
    }
    if (!accepted) {
      await page.goto(base + '/p3-a/open/short');
      await expect(page.locator('#interview-textarea')).toBeEnabled();
      await expect(page.locator('#interview-textarea')).toHaveValue('');
      const statusUrl = base + `/users/assessment/m5/situations/${asId}/answer-status?request_id=${operation.requestId}&turn_id=${operation.turnId}`;
      expect((await page.request.get(statusUrl)).status()).toBe(403);
      expect((await page.request.get(base + runtimePath)).status()).toBe(403);
      await context.clearCookies();
      expect((await page.request.get(statusUrl)).status()).toBe(401);
      await page.goto(base + '/p3-a/open/long');
      await expect(page.locator('#interview-panel')).toBeVisible();
      await expect(input).toHaveValue(text);
      expect((await pending(page))[0].requestId).toBe(operation.requestId);
    }
    const copied = await page.evaluate(() => Object.entries(sessionStorage));
    const tab = await context.newPage();
    await tab.addInitScript((entries) => entries.forEach(([key, value]) => sessionStorage.setItem(key, value)), copied);
    await tab.goto(page.url());
    await expect(tab.locator('#interview-panel')).toBeVisible();
    if (accepted) {
      await expect(tab.locator('.interview-message.own').filter({ hasText: text })).toHaveCount(1);
      // Accepted readback may resolve the pending operation without a POST.
      await expect.poll(() => pending(page)).toHaveLength(0);
    } else {
      const retry = page.locator('.interview-message.own').filter({ hasText: text }).locator('.interview-message-retry');
      await page.setViewportSize({ width: 320, height: 568 });
      await expect(retry).toBeVisible();
      await retry.focus(); await expect(retry).toBeFocused();
      await page.keyboard.press('Enter');
      await expect(input).toHaveValue(''); await expect(submit).toBeEnabled();
      expect(requests).toHaveLength(2); expect(requests[1]).toEqual(requests[0]);
    }
    await page.unroute('**' + turnsPath);
    const after = pg(`ordinary-${accepted ? 'lost-after-commit' : 'aborted-before-commit'}-recovered`);
    expect(after.turns.filter((turn) => turn.content_text === text)).toHaveLength(1);
    expect(after.turns.find((turn) => turn.content_text === text).request_id).toBe(requests[0].request_id);
    // C4/C5 two concurrent identical replay requests; repeat again after reload.
    await Promise.all([sameKey(page, turnsPath, requests[0]), sameKey(tab, turnsPath, requests[0])]);
    await page.reload(); await expect(page.locator('#interview-panel')).toBeVisible();
    await sameKey(page, turnsPath, requests[0]);
    await sameKey(page, turnsPath, { ...requests[0], content: text + ' изменён' }, 409);
    assertNoExtraEffects(after, pg(`ordinary-${accepted ? 'accepted' : 'absent'}-replay-conflict`));
    await saveScreenshot(page, `ordinary-${accepted ? 'accepted' : 'absent'}-recovered`);
    await tab.close();
  }
});

test('EXEC03 C7 M7 ASK: phase isolation, lost commit response, reload, immutable endpoint and one answer/handoff', async ({ page, context }) => {
  test.setTimeout(180000);
  await open(page);
  // One tab has only a draft; another has an unknown command that never reached
  // the server. The same AS advances to ASK through real accepted commands.
  const draftTab = await context.newPage(); await open(draftTab);
  await draftTab.locator('#interview-textarea').fill('EXEC03 ordinary draft must not become ASK');
  let absentOperation;
  await page.route('**' + turnsPath, async (route) => {
    absentOperation = (await pending(page))[0];
    return route.abort('failed');
  });
  await page.locator('#interview-textarea').fill('EXEC03 absent old phase');
  await page.locator('#interview-submit-button').click();
  await expect.poll(() => Boolean(absentOperation)).toBe(true);
  await page.unroute('**' + turnsPath);
  // Real ordinary answer + scenario end create the M6/M7 chain. No result rows or
  // decision statuses are inserted by the test; the isolated technical gateway runs it.
  await sameKey(page, turnsPath, { request_id: 'exec03-ask-seed-' + randomUUID(), turn_id: randomUUID(), content: fixture.answer });
  await sameKey(page, `/users/assessment/m5/situations/${asId}/transitions`,
    { request_id: 'exec03-ask-end-' + randomUUID(), action: 'scenario_end', reason: 'synthetic_exec03_precondition' });
  await expect.poll(async () => (await runtime(page)).clarification?.status, { timeout: 120000, intervals: [250, 1000] }).toBe('ASK');
  const before = await runtime(page);
  const decisionId = before.clarification.id;
  const endpoint = `/users/assessment/m7/clarifications/${decisionId}/answers`;
  await page.reload(); await expect(page.locator('#interview-textarea')).toBeEnabled();
  await expect(page.locator('#interview-textarea')).toHaveValue('');
  await expect.poll(() => pending(page)).toHaveLength(0);
  const resolved = await page.evaluate(() => Object.entries(sessionStorage)
    .filter(([key]) => key.includes(':resolved:')).map(([, value]) => JSON.parse(value)));
  expect(resolved.some((item) => item.requestId === absentOperation.requestId
    && item.endpoint === turnsPath && item.resolution === 'absent_in_previous_phase')).toBe(true);
  await draftTab.reload(); await expect(draftTab.locator('#interview-textarea')).toBeEnabled();
  await expect(draftTab.locator('#interview-textarea')).toHaveValue('');
  await draftTab.close();
  await expect(page.locator('#interview-messages')).toContainText(before.clarification.question.text);
  const text = `Уточнение EXEC03: ${fixture.clarification_answer}`;
  let body; let operation; let attempts = 0; let committed = false; let releaseReceipt;
  const receiptGate = new Promise((resolve) => { releaseReceipt = resolve; });
  const sentBodies = [];
  await page.route('**' + endpoint, async (route) => {
    body = route.request().postDataJSON(); sentBodies.push(body); attempts += 1;
    operation = (await pending(page)).find((item) => item.requestId === body.request_id);
    if (attempts === 1) return route.abort('failed'); // No server dispatch.
    const response = await route.fetch(); expect(response.status()).toBe(200);
    committed = true;
    await receiptGate; // The AS will close before this real response is lost.
    return route.abort('failed');
  });
  await page.locator('#interview-textarea').fill(text);
  await page.locator('#interview-submit-button').click();
  await expect.poll(() => attempts).toBe(1);
  await expect(page.locator('#interview-error')).toBeVisible();
  expect(operation).toBeTruthy();
  expect(operation.clarificationId).toBe(decisionId); expect(operation.endpoint).toBe(endpoint);
  askAcceptedBody = body; askAcceptedEndpoint = endpoint;
  for (let n = 0; n < 2; n += 1) {
    await page.reload(); await expect(page.locator('#interview-panel')).toBeVisible();
    await expect(page.locator('#interview-textarea')).toHaveValue(text);
    expect((await pending(page))[0].requestId).toBe(operation.requestId);
  }
  const copied = await page.evaluate(() => Object.entries(sessionStorage));
  const recoveryTab = await context.newPage();
  await recoveryTab.addInitScript((entries) => entries.forEach(([key, value]) => sessionStorage.setItem(key, value)), copied);
  await recoveryTab.goto(page.url());
  await expect(recoveryTab.locator('.interview-message-retry')).toBeVisible();
  await page.locator('.interview-message-retry').click();
  await expect.poll(() => committed).toBe(true);
  expect(sentBodies[1]).toEqual(sentBodies[0]);
  await sameKey(recoveryTab, endpoint, body);
  await expect.poll(async () => (await runtime(page)).finish_availability?.allowed, { timeout: 30000 }).toBe(true);
  const closedBeforeLoss = await page.request.post(base + `/users/assessment/m7/cycles/${cycleId}/finish-situation`,
    { data: { idempotency_key: 'exec03-ask-close-before-response-loss-' + randomUUID() } });
  expect(closedBeforeLoss.status()).toBe(200);
  pg('ask-committed-closed-before-response-loss');
  releaseReceipt();
  await expect.poll(async () => (await runtime(page)).between_situations).toBe(true);
  for (let n = 0; n < 2; n += 1) {
    await page.reload(); await expect(page.locator('#interview-panel')).toBeVisible();
    await expect(page.locator('#interview-textarea')).toHaveValue('');
    await expect.poll(() => pending(page)).toHaveLength(0);
  }
  await recoveryTab.close(); await page.unroute('**' + endpoint);
  await expect.poll(() => pg('ask-analysis-settled').unsettled_jobs, { timeout: 30000 }).toBe(0);
  const saved = pg('ask-lost-response-recovered');
  expect(saved.turns.filter((turn) => turn.content_text === text)).toHaveLength(1);
  const response = saved.clarifications.find((item) => item.id === decisionId);
  expect(response.request_id).toBe(body.request_id); expect(response.answer_turn_id).toBe(body.turn_id);
  expect(response.outcome).toBe('answered'); expect(response.handoff_id).toBeTruthy();
  await sameKey(page, endpoint, body);
  await sameKey(page, endpoint, { ...body, content: text + ' изменён' }, 409);
  if (process.env.EXEC03_WITH_FIX01 === '1') await sameKey(page, endpoint, { ...body, turn_id: randomUUID() }, 409);
  else test.info().annotations.push({ type: 'EXEC01_dependency', description: 'Strict changed-turn replay is verified in composed 01+03, base46a5532 returns200; content conflict is checked here.' });
  assertNoExtraEffects(saved, pg('ask-replay-conflict'));
  await saveScreenshot(page, 'ask-recovered');
});


test('EXEC03 C8/C9 with EXEC01: next AS isolation, original receipts after close and exhausted budget', async ({ page }) => {
  test.skip(process.env.EXEC03_WITH_FIX01 !== '1', 'Requires the separate EXEC01 candidate for shared admission/replay');
  test.setTimeout(180000);
  await page.goto(base + '/p3-a/open/long');
  if (!(await runtime(page)).between_situations) {
  await expect.poll(async () => (await runtime(page)).finish_availability?.allowed, { timeout: 30000 }).toBe(true);
  const finish = await page.request.post(base + `/users/assessment/m7/cycles/${cycleId}/finish-situation`,
    { data: { idempotency_key: 'exec03-finish-' + randomUUID() } });
  expect(finish.status()).toBe(200);
  }
  await page.reload();
  await page.getByRole('button', { name: 'Приступить к следующей ситуации', exact: true }).click();
  await expect.poll(async () => { const id = (await runtime(page)).current_situation?.assessment_situation_id;
    return Boolean(id && id !== asId); }, { timeout: 60000 }).toBe(true);
  const next = await runtime(page);
  const nextAsId = next.current_situation?.assessment_situation_id;
  expect(nextAsId).toBeTruthy(); expect(nextAsId).not.toBe(asId);
  await expect(page.locator('#interview-textarea')).toBeEnabled();
  await expect(page.locator('#interview-textarea')).toHaveValue('');
  expect((await pending(page)).every((item) => item.situationId !== asId)).toBe(true);
  await expect.poll(() => pg('closed-original-settled').unsettled_jobs, { timeout: 30000 }).toBe(0);
  const closed = pg('closed-original-before-replay');
  expect(closed.status).toBe('closed');
  for (const [endpoint, body] of [[turnsPath, ordinaryAcceptedBody], [askAcceptedEndpoint, askAcceptedBody]]) {
    await sameKey(page, endpoint, body);
    await sameKey(page, endpoint, { ...body, content: body.content + ' changed' }, 409);
    await sameKey(page, endpoint, { ...body, request_id: randomUUID(), turn_id: randomUUID() }, 409);
    const clarification = endpoint === askAcceptedEndpoint ? `&clarification_id=${endpoint.split('/').at(-2)}` : '';
    const status = await page.request.get(base + `/users/assessment/m5/situations/${asId}/answer-status?request_id=${body.request_id}&turn_id=${body.turn_id}${clarification}`);
    expect(status.status()).toBe(200); expect(status.headers()['cache-control']).toBe('no-store');
    expect((await status.json()).status).toBe('accepted');
  }
  assertNoExtraEffects(closed, pg('closed-original-after-replay'));
  const nextEndpoint = `/users/assessment/m5/situations/${nextAsId}/turns`;
  const timeBody = { request_id: randomUUID(), turn_id: randomUUID(), content: 'EXEC03 accepted before budget boundary' };
  let committed = false; let releaseLostReceipt; let operation;
  const gate = new Promise((resolve) => { releaseLostReceipt = resolve; });
  await page.route('**' + nextEndpoint, async (route) => {
    const posted = route.request().postDataJSON();
    Object.assign(timeBody, posted);
    operation = (await pending(page)).find((item) => item.requestId === posted.request_id);
    const accepted = await route.fetch(); expect(accepted.status()).toBe(200);
    committed = true; await gate; return route.abort('failed');
  });
  await page.locator('#interview-textarea').fill(timeBody.content);
  await page.locator('#interview-submit-button').click();
  await expect.poll(() => committed).toBe(true);
  expect(operation.turnId).toBe(timeBody.turn_id);
  const beforeClock = pg('budget-accepted-response-held-before-clock', nextAsId);
  const clock = spawnSync(python, [path.join(root, 'tests/frontend/exec03_clock_fixture.py'),
    '--root', root, '--state', statePath, '--as-id', nextAsId], { cwd: root, env: process.env, encoding: 'utf8' });
  expect(clock.status, clock.stderr).toBe(0);
  expect(JSON.parse(clock.stdout).time_budget_seconds).toBe(7200);
  expect(JSON.parse(clock.stdout).calendar_window_seconds).toBe(259200);
  fs.writeFileSync(path.join(evidence, 'budget-clock-input.json'), clock.stdout);
  // New-write admission persists expiry while the original accepted transport
  // response is still held. Then lose it and recover after a real reload.
  await sameKey(page, nextEndpoint, { ...timeBody, request_id: randomUUID(), turn_id: randomUUID() }, 409);
  pg('budget-closed-before-response-loss', nextAsId);
  releaseLostReceipt();
  await page.reload();
  await expect.poll(() => pending(page), { timeout: 15000 }).toHaveLength(0);
  await page.unroute('**' + nextEndpoint);
  await sameKey(page, nextEndpoint, timeBody);
  await sameKey(page, nextEndpoint, { ...timeBody, content: timeBody.content + ' changed' }, 409);
  const afterClock = pg('budget-after-replay-new-write-rejected', nextAsId);
  expect(afterClock.turns).toEqual(beforeClock.turns);
  expect(afterClock.operations).toEqual(beforeClock.operations);
  const boundaryEvents = new Set(['interaction_terminated', 'assessment_situation_closed']);
  expect(afterClock.events.filter((item) => !boundaryEvents.has(item.event_type))).toEqual(beforeClock.events);
  expect(afterClock.events.filter((item) => boundaryEvents.has(item.event_type))).toHaveLength(2);
  expect(afterClock.c45_handoffs).toHaveLength(beforeClock.c45_handoffs.length + 1);
  const readback = await page.request.get(base + `/users/assessment/m5/situations/${nextAsId}/answer-status?request_id=${timeBody.request_id}&turn_id=${timeBody.turn_id}`);
  expect(readback.status()).toBe(200); expect((await readback.json()).status).toBe('accepted');
  await saveScreenshot(page, 'budget-new-write-rejected');
});
