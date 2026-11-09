import { test, expect } from '@playwright/test';
import { spawn, spawnSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { createHash, randomUUID } from 'node:crypto';

// Real main.app HTTP + owned PostgreSQL. Only long public-AS input and upstream
// plan policy are explicit component fixtures; no API response route.fulfill.
const root = process.cwd();
const python = process.env.BROWSER_PYTHON || path.join(root, '.venv/bin/python');
const externalState = process.env.P3_A_STATE || '';
const directory = externalState ? path.dirname(externalState)
  : path.join(root, '.test-stand/p3-a', randomUUID());
const statePath = externalState || path.join(directory, 'state.json');
const evidence = process.env.P3_A_EVIDENCE || path.join(directory, 'evidence');
let server, state, base;

function cli(action) {
  const result = spawnSync(python, ['scripts/p3-a-preview.py', action, '--state', statePath,
    '--port', process.env.P3_A_PORT || '18933'], { cwd: root, encoding: 'utf8' });
  fs.appendFileSync(path.join(directory, 'prepare.log'), result.stdout + result.stderr);
  if (result.status !== 0) throw new Error(`P3-A ${action}: ${result.stderr}`);
}

test.beforeAll(async () => {
  if (!process.env.STAND_ADMIN_URL) throw new Error('Explicit owned localhost STAND_ADMIN_URL required');
  fs.mkdirSync(directory, { recursive: true }); fs.mkdirSync(evidence, { recursive: true });
  if (!externalState) cli('create');
  state = JSON.parse(fs.readFileSync(statePath, 'utf8'));
  base = `http://127.0.0.1:${state.port}`;
  if (!externalState) {
    const log = fs.openSync(path.join(directory, 'app.log'), 'a');
    server = spawn(python, ['scripts/p3-a-preview.py', 'serve', '--state', statePath],
      { cwd: root, stdio: ['ignore', log, log] }); fs.closeSync(log);
  }
  await expect.poll(async () => { try { return (await fetch(`${base}/health/ready`)).status; } catch { return 0; } },
    { timeout: 30000 }).toBe(200);
  const identity = await (await fetch(`${base}/p3-a/identity`)).json();
  expect(identity.run_id).toBe(state.run_id); expect(identity.fixture).toBe('p3-a-saved-public-as/1');
  for (const [file, hash] of Object.entries(identity.startup_fingerprints)) {
    expect(createHash('sha256').update(fs.readFileSync(path.join(root, file))).digest('hex'), file).toBe(hash);
  }
  fs.writeFileSync(path.join(evidence, 'source-identity.json'), JSON.stringify(identity, null, 2) + '\n');
});

test.afterAll(async () => {
  let readbackError;
  if (state && fs.existsSync(statePath)) {
    const readback = spawnSync(python, ['scripts/p3-a-preview.py', 'inspect', '--state', statePath],
      { cwd: root, encoding: 'utf8' });
    if (readback.status === 0) fs.writeFileSync(path.join(evidence, 'pg-readback.json'), readback.stdout);
    else readbackError = new Error(`P3-A readback: ${readback.stderr}`);
  }
  if (server && server.exitCode === null) {
    const ended = new Promise((resolve) => server.once('exit', resolve));
    server.kill('SIGTERM');
    await Promise.race([ended, new Promise((resolve) => setTimeout(resolve, 5000))]);
    if (server.exitCode === null) { server.kill('SIGKILL'); await ended; }
  }
  if (!externalState && fs.existsSync(statePath)) cli('destroy');
  if (readbackError) throw readbackError;
});

test.beforeEach(async ({ page }, info) => {
  info.annotations.push({ type: 'scope', description:
    'P3-A saved synthetic AS: real HTTP/PG; test-only public input + legacy component plan policy; NOT AC18 PATH/pilot admission/physical keyboard.' });
  page.on('dialog', (dialog) => dialog.accept());
  page.p3aResponses = [];
  page.on('response', async (response) => {
    const pathname = new URL(response.url()).pathname;
    if (!pathname.startsWith('/users/assessment/') || response.request().method() !== 'POST') return;
    try { page.p3aResponses.push({ pathname, status: response.status(), body: await response.json() }); } catch { /* navigation */ }
  });
});

test.afterEach(async ({ page }, info) => {
  await info.attach('assessment-http', { body: JSON.stringify(page.p3aResponses, null, 2), contentType: 'application/json' });
});

async function open(page, mode = 'long') {
  await page.goto(`${base}/p3-a/open/${mode}`);
  await expect(page.locator('#interview-panel')).toBeVisible();
  await expect(page.locator('.interview-message--situation')).toHaveCount(1);
  await page.evaluate(() => document.fonts.ready);
}

async function runtime(page, kind = 'long') {
  const response = await page.request.get(`${base}/users/assessment/cycles/${state.p3_a_previews[kind].cycle_id}/runtime`);
  expect(response.ok()).toBe(true);
  return response.json();
}

async function geometry(page) {
  return page.evaluate(() => {
    const rect = (selector) => {
      const node = document.querySelector(selector), box = node.getBoundingClientRect();
      const x = Math.max(0, Math.min(innerWidth - 1, box.left + box.width / 2));
      const y = Math.max(0, Math.min(innerHeight - 1, box.top + Math.min(box.height / 2, 20)));
      const top = document.elementFromPoint(x, y);
      return { x: box.x, y: box.y, width: box.width, height: box.height,
        scrollTop: node.scrollTop, scrollHeight: node.scrollHeight, clientHeight: node.clientHeight,
        hit: top === node || node.contains(top) };
    };
    return { viewport: { width: innerWidth, height: innerHeight },
      visualViewport: visualViewport ? { width: visualViewport.width, height: visualViewport.height, scale: visualViewport.scale } : null,
      document: { scrollWidth: document.documentElement.scrollWidth, scrollHeight: document.documentElement.scrollHeight },
      input: rect('#interview-textarea'), submit: rect('#interview-submit-button'),
      history: rect('#interview-scroll-area'), actions: rect('.interview-action-buttons') };
  });
}

async function capture(page, name) {
  const metrics = await geometry(page);
  fs.writeFileSync(path.join(evidence, `${name}.json`), JSON.stringify(metrics, null, 2) + '\n');
  await page.screenshot({ path: path.join(evidence, `${name}.png`), fullPage: false });
  return metrics;
}

test('P3-AC01/02 short and long saved AS: authors, public materials, five widths and reachable controls', async ({ page }) => {
  for (const kind of ['short', 'long']) {
    await open(page, kind);
    for (const width of [320, 390, 430, 768, 1440]) {
      await page.setViewportSize({ width, height: width >= 768 ? 1000 : 844 });
      await expect(page.locator('.interview-message--situation')).toHaveCount(1);
      await expect(page.locator('.interview-message--situation [data-speaker-label="4К Ассистент"]')).toHaveCount(1);
      await expect(page.locator('.case-sidebar')).toHaveCount(0);
      await expect(page.locator('#interview-panel .panel-stepper')).toHaveCount(0);
      await expect(page.locator('.interview-message--situation')).not.toContainText('execution_payload');
      await expect(page.locator('.interview-message--situation')).not.toContainText('indicator_targets');
      await page.locator('#interview-textarea').scrollIntoViewIfNeeded();
      await page.locator('#interview-submit-button').scrollIntoViewIfNeeded();
      const metrics = await capture(page, `${kind}-${width}`);
      expect(metrics.document.scrollWidth).toBeLessThanOrEqual(width + 1);
      expect(metrics.input.hit).toBe(true);
      expect(metrics.submit.hit).toBe(true);
      expect(metrics.submit.height).toBe(48);
      if (width <= 430) expect(Math.abs(metrics.submit.width - metrics.actions.width)).toBeLessThanOrEqual(1);
      await page.locator('#interview-pause-button').click({ trial: true });
      await page.locator('#interview-finish-button').click({ trial: true });
      if (kind === 'long') {
        const last = page.locator('.interview-message--situation li').last();
        await last.scrollIntoViewIfNeeded(); await expect(last).toBeInViewport();
        await page.screenshot({ path: path.join(evidence, `${kind}-${width}-last-material.png`), fullPage: false });
      }
    }
    const cdp = await page.context().newCDPSession(page);
    try {
      await cdp.send('Emulation.setPageScaleFactor', { pageScaleFactor: 2 });
      const scaled = await capture(page, `${kind}-emulated-page-scale-200`);
      expect(scaled.visualViewport.scale).toBeCloseTo(2, 1);
      fs.writeFileSync(path.join(evidence, `${kind}-zoom-scope.json`), JSON.stringify({
        mode: 'Chromium CDP pageScaleFactor=2',
        limitation: 'Emulated page scale; NOT physical device, OS magnification or browser text-zoom acceptance.',
      }, null, 2) + '\n');
    } finally { await cdp.send('Emulation.setPageScaleFactor', { pageScaleFactor: 1 }); await cdp.detach(); }
  }
});

test('P3-AC02/03 multiline draft survives reload, reduced viewport, rotation and Cycle/AS scope', async ({ page }) => {
  await open(page);
  const input = page.locator('#interview-textarea');
  const draft = 'Синтетический черновик\nВторая строка: условия и зависимости.\nНепринятый текст.';
  await input.fill(draft); await input.focus();
  await page.setViewportSize({ width: 390, height: 430 }); // reduced viewport, not a physical keyboard
  await expect(input).toBeFocused(); await expect(input).toHaveValue(draft);
  await input.scrollIntoViewIfNeeded();
  const reduced = await capture(page, 'draft-reduced-viewport');
  expect(reduced.input.hit).toBe(true);
  await page.setViewportSize({ width: 844, height: 390 });
  await expect(input).toBeFocused(); await expect(input).toHaveValue(draft);
  await page.reload(); await expect(input).toHaveValue(draft);
  const model = await runtime(page);
  expect(model.trace.turns.filter((turn) => turn.content_text === draft)).toHaveLength(0);
  await open(page, 'short'); await expect(input).toHaveValue('');
  await open(page, 'long'); await expect(input).toHaveValue(draft);
});

test('P3-AC03 send persists once over real HTTP/PG; send leaves AS active and reload restores history', async ({ page }) => {
  await open(page, 'short');
  const input = page.locator('#interview-textarea');
  const answer = JSON.parse(fs.readFileSync('tests/browser/fixtures/v1.json')).answer;
  const before = await runtime(page, 'short');
  const previous = before.trace.turns.filter((turn) => turn.speaker_type === 'assessee').length;
  await input.fill(answer);
  const response = page.waitForResponse((reply) => /\/m5\/situations\/[^/]+\/turns$/.test(new URL(reply.url()).pathname)
    && reply.request().method() === 'POST');
  await page.locator('#interview-submit-button').click();
  expect((await response).ok()).toBe(true);
  await expect.poll(async () => (await runtime(page, 'short')).trace.turns.filter((turn) => turn.speaker_type === 'assessee').length)
    .toBe(previous + 1);
  const after = await runtime(page, 'short');
  expect(after.current_situation.status).toBe('active');
  expect(after.status.collection_status).toBe('active');
  const saved = after.trace.turns.filter((turn) => turn.speaker_type === 'assessee').at(-1);
  await expect(page.locator(`[data-turn-id="${saved.turn_id}"]`)).toHaveCount(1);
  await page.reload();
  await expect(page.locator(`[data-turn-id="${saved.turn_id}"]`)).toHaveCount(1);
  await expect(page.locator('.interview-message--situation')).toHaveCount(1);
  await expect(input).toHaveValue('');
  await capture(page, 'saved-turn-after-reload');
});

test('P3-AC10 partial: server control pause/resume, delayed/unknown response and restored history', async ({ page }, info) => {
  info.annotations.push({ type: 'not_prepared', description:
    'R1 explicit return-state/return-continue is NOT_PREPARED pending P3-B checkpoint; control resume is a separate existing command.' });
  await open(page, 'paused');
  await expect(page.locator('#interview-textarea')).toBeDisabled();
  await expect(page.locator('#interview-timer-badge')).toContainText('Пауза');
  await capture(page, 'confirmed-pause');
  const resume = page.locator('#interview-pause-button');
  await expect(resume).toContainText('Продолжить');
  await resume.click(); await expect(page.locator('#interview-textarea')).toBeEnabled();
  for (const mode of ['delayed', 'unknown']) {
    await open(page, mode);
    const answer = `Синтетический ответ P3-A ${mode} ${randomUUID()}`;
    await page.locator('#interview-textarea').fill(answer);
    const pending = page.waitForResponse((reply) => /\/m5\/situations\/[^/]+\/turns$/.test(new URL(reply.url()).pathname)
      && reply.request().method() === 'POST');
    await page.locator('#interview-submit-button').click();
    if (mode === 'delayed') {
      await expect(page.locator('#interview-submit-button')).toBeDisabled();
      await capture(page, 'delivery-delayed');
    }
    expect((await pending).status()).toBe(mode === 'unknown' ? 503 : 200);
    await expect.poll(async () => (await runtime(page)).trace.turns.filter((turn) => turn.content_text === answer).length).toBe(1);
    if (mode === 'unknown') {
      const observation = {
        scope: 'real commit / lost-response observation; no repeated submit',
        server_accepted_turns: (await runtime(page)).trace.turns.filter((turn) => turn.content_text === answer).length,
        input_contains_accepted_answer: (await page.locator('#interview-textarea').inputValue()) === answer,
        send_enabled: await page.locator('#interview-submit-button').isEnabled(),
        delivery_labels: await page.locator('.interview-message-delivery-status').allTextContents(),
      };
      observation.safety_status = observation.input_contains_accepted_answer && observation.send_enabled
        ? 'FAIL_ACCEPTED_TURN_CAN_BE_RESENT_AS_DRAFT' : 'REQUIRES_REVIEW';
      fs.writeFileSync(path.join(evidence, 'unknown-delivery-observation.json'), JSON.stringify(observation, null, 2) + '\n');
      await capture(page, 'delivery-unknown-before-reload');
      info.annotations.push({ type: 'unknown_delivery_safety', description: observation.safety_status });
    }
    await page.reload();
    await expect(page.locator('.interview-message.own').filter({ hasText: answer })).toHaveCount(1);
    await capture(page, `delivery-${mode}-readback`);
  }
  await open(page, 'restored');
  await expect(page.locator('.interview-message.own')).not.toHaveCount(0);
  await capture(page, 'restored-dialogue');
});

test('P3-AC02 saved new trace preserves reading position until the participant requests latest messages', async ({ page }) => {
  await open(page, 'long');
  const history = page.locator('#interview-scroll-area');
  await history.scrollIntoViewIfNeeded();
  await page.waitForTimeout(400); // initial RAF/legacy delayed alignment must finish
  await history.evaluate((node) => { node.scrollTop = 320; });
  const before = await history.evaluate((node) => node.scrollTop);
  const answer = `Синтетическая новая сохранённая реплика ${randomUUID()}`;
  const accepted = await page.request.post(`${base}/users/assessment/m5/situations/${state.p3_a_previews.long.assessment_situation_id}/turns`, {
    data: { request_id: randomUUID(), turn_id: randomUUID(), content: answer },
  });
  expect(accepted.ok()).toBe(true);
  await expect(page.locator('.interview-message.own').filter({ hasText: answer })).toHaveCount(1);
  const after = await history.evaluate((node) => node.scrollTop);
  expect(Math.abs(after - before)).toBeLessThanOrEqual(2);
  await capture(page, 'new-trace-keeps-reading');
  const latest = page.locator('#interview-messages-scroll');
  await expect(latest).toBeVisible();
  await latest.click();
  await expect(page.locator('.interview-message.own').filter({ hasText: answer })).toBeInViewport();
  await capture(page, 'new-trace-request-latest');
});
