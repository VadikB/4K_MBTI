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
      history: rect('#interview-scroll-area'), actions: rect('.interview-action-buttons'),
      overflow_offenders: [...document.querySelectorAll('#interview-panel *')].map((node) => {
        const box = node.getBoundingClientRect(), computed = getComputedStyle(node);
        return { tag: node.tagName, id: node.id, class: node.className, left: box.left, right: box.right,
          width: box.width, font_px: computed.fontSize, white_space: computed.whiteSpace };
      }).filter((item) => item.width > 0 && (item.right > innerWidth + 1 || item.left < -1)).slice(0, 20) };
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
  info.annotations.push({ type: 'control_scenario', description:
    'Control pause/resume is a separate existing command; initial R1v2 explicit return-state/return-continue is tested separately in p3-a-r1-return.spec.mjs.' });
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
        ? 'FAIL_ACCEPTED_TURN_CAN_BE_RESENT_AS_DRAFT'
        : !observation.input_contains_accepted_answer && !observation.send_enabled
          && !observation.delivery_labels.includes('Не отправлено')
          ? 'PASS_SAVED_TURN_GUARDED_PENDING_EXPLICIT_RECOVERY' : 'REQUIRES_REVIEW';
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
  await history.evaluate((node) => { node.scrollTo({ top: 320, behavior: 'instant' }); });
  await expect.poll(() => history.evaluate((node) => node.scrollTop)).toBe(320);
  const before = await history.evaluate((node) => node.scrollTop);
  const answer = `Синтетическая новая сохранённая реплика ${randomUUID()}`;
  const accepted = await page.request.post(`${base}/users/assessment/m5/situations/${state.p3_a_previews.long.assessment_situation_id}/turns`, {
    data: { request_id: randomUUID(), turn_id: randomUUID(), content: answer },
  });
  expect(accepted.ok()).toBe(true);
  await expect(page.locator('.interview-message.own').filter({ hasText: answer })).toHaveCount(1);
  const after = await history.evaluate((node) => node.scrollTop);
  fs.writeFileSync(path.join(evidence, 'new-trace-scroll-observation.json'), JSON.stringify({
    before, after, expected_max_delta: 2, setup: 'scrollTo instant; confirmed reached320 before submitting the other-tab turn',
  }, null, 2) + '\n');
  expect(Math.abs(after - before)).toBeLessThanOrEqual(2);
  await capture(page, 'new-trace-keeps-reading');
  const latest = page.locator('#interview-messages-scroll');
  await expect(latest).toBeVisible();
  await latest.click();
  await expect(page.locator('.interview-message.own').filter({ hasText: answer })).toBeInViewport();
  await capture(page, 'new-trace-request-latest');
});

test('P3-AC02 synthetic computed text scale 200 percent keeps conditions and controls reachable', async ({ page }, info) => {
  info.annotations.push({ type: 'emulation', description:
    'Synthetic computed font-size/line-height ×2 with absolute px values captured before mutation; NOT native browser text zoom, OS magnification or physical-device acceptance.' });
  for (const width of [320, 390, 1440]) {
    await page.setViewportSize({ width, height: width >= 768 ? 1000 : 844 });
    await open(page, 'long');
    const situation = page.locator('.interview-message--situation');
    const essential = await situation.textContent();
    const draft = `Синтетический черновик при размере текста 200%: ${width}\nВторая строка.`;
    const input = page.locator('#interview-textarea'); await input.fill(draft); await input.focus();
    const fonts = await page.evaluate(() => {
      const elements = [...document.querySelectorAll('#interview-panel *')].filter((element) =>
        element.tagName === 'TEXTAREA' || [...element.childNodes].some((node) =>
          node.nodeType === Node.TEXT_NODE && node.textContent.trim()));
      // Snapshot all original metrics first: inherited scaling must not compound.
      const values = elements.map((element) => {
        const computed = getComputedStyle(element), size = parseFloat(computed.fontSize);
        const line = parseFloat(computed.lineHeight);
        return { element, size, line: Number.isFinite(line) ? line : size * 1.5 };
      });
      for (const value of values) {
        value.element.style.fontSize = `${value.size * 2}px`;
        value.element.style.lineHeight = `${value.line * 2}px`;
      }
      return { mode: 'synthetic computed text scale200percent; absolute px, no nested compounding',
        elements_scaled: values.length, textarea_font_px: parseFloat(getComputedStyle(document.querySelector('#interview-textarea')).fontSize),
        situation_fonts_px: [...new Set([...document.querySelectorAll('.interview-message--situation p, .interview-message--situation li')]
          .map((element) => parseFloat(getComputedStyle(element).fontSize)))] };
    });
    expect(fonts.textarea_font_px).toBe(32); expect(fonts.situation_fonts_px).toContain(32);
    await expect(situation).toHaveText(essential);
    const last = situation.locator('li').last(); await last.scrollIntoViewIfNeeded(); await expect(last).toBeInViewport();
    await expect(input).toHaveValue(draft); await expect(input).toBeFocused();
    await input.scrollIntoViewIfNeeded(); const inputMetrics = await geometry(page); expect(inputMetrics.input.hit).toBe(true);
    await page.locator('#interview-submit-button').click({ trial: true });
    const submitMetrics = await capture(page, `synthetic-text-200-${width}`); expect(submitMetrics.submit.hit).toBe(true);
    expect(submitMetrics.document.scrollWidth).toBeLessThanOrEqual(width + 1);
    await expect(input).toHaveValue(draft); await expect(input).toBeFocused();
    fs.writeFileSync(path.join(evidence, `synthetic-text-200-${width}-scope.json`), JSON.stringify({
      ...fonts, essential_text_unchanged: (await situation.textContent()) === essential,
      input_reachable: inputMetrics.input.hit, submit_reachable: submitMetrics.submit.hit,
      native_browser_text_zoom: 'NOT_RUN', physical_keyboard: 'NOT_RUN',
    }, null, 2) + '\n');
  }
});

for (const fault of ['lost-after-commit', 'aborted-before-commit']) {
  test(`P3-AC03 delivery ${fault}: reload and double retry preserve one request identity and one saved Turn`, async ({ page }) => {
    await open(page, fault === 'lost-after-commit' ? 'unknown' : 'long');
    const answer = `Синтетическая проверка доставки ${fault} ${randomUUID()}`;
    const requests = [];
    await page.route('**/users/assessment/m5/situations/*/turns', async (route) => {
      const payload = route.request().postDataJSON(); requests.push(payload);
      if (fault === 'aborted-before-commit' && requests.length === 1) return route.abort('failed');
      // A transport delay keeps an actual double click within one pending attempt.
      await new Promise((resolve) => setTimeout(resolve, 200));
      return route.continue();
    });
    const input = page.locator('#interview-textarea'), submit = page.locator('#interview-submit-button');
    await input.fill(answer); await submit.click();
    await expect.poll(() => requests.length).toBe(1);
    const savedCount = async () => (await runtime(page)).trace.turns.filter((turn) => turn.content_text === answer).length;
    await expect.poll(savedCount).toBe(fault === 'lost-after-commit' ? 1 : 0);
    await expect(submit).toBeDisabled();
    await expect(input).toHaveValue(fault === 'aborted-before-commit' ? answer : '');
    await page.reload(); await expect(page.locator('#interview-panel')).toBeVisible();
    await expect(submit).toBeDisabled();
    await expect(input).toHaveValue(fault === 'aborted-before-commit' ? answer : '');
    const operationRow = page.locator('.interview-message.own').filter({ hasText: answer });
    await expect(operationRow).toHaveCount(1);
    await expect(operationRow).not.toContainText('Не отправлено');
    const retry = operationRow.locator('.interview-message-retry'); await expect(retry).toBeVisible();
    await page.context().addCookies([{ name: 'p3_a_delivery', value: 'normal', url: base,
      httpOnly: true, sameSite: 'Strict' }]);
    await retry.dblclick({ delay: 10 });
    await expect(submit).toBeEnabled(); await expect(input).toHaveValue('');
    await expect.poll(savedCount).toBe(1);
    expect(requests).toHaveLength(2);
    expect(new Set(requests.map((request) => request.request_id)).size).toBe(1);
    expect(new Set(requests.map((request) => request.turn_id)).size).toBe(1);
    expect(new Set(requests.map((request) => request.content))).toEqual(new Set([answer]));
    await expect(page.locator('.interview-message.own').filter({ hasText: answer })).toHaveCount(1);
    await expect(page.locator('.interview-message.own.delivery-failed')).toHaveCount(0);
    await page.reload(); await expect(input).toHaveValue(''); await expect(submit).toBeEnabled();
    await expect(page.locator('.interview-message.own').filter({ hasText: answer })).toHaveCount(1);
    fs.writeFileSync(path.join(evidence, `delivery-${fault}-identity.json`), JSON.stringify({
      transport_fault: fault, requests, saved_turns: await savedCount(),
      one_identity: true, accepted_answer_not_a_draft: true, double_retry_guarded: true,
    }, null, 2) + '\n');
    await capture(page, `delivery-${fault}-recovered`);
  });
}

test('P3-AC03 failed sender preflight makes zero POSTs and permits an edited draft to be sent once', async ({ page }) => {
  await open(page, 'long');
  const input = page.locator('#interview-textarea'), submit = page.locator('#interview-submit-button');
  const initial = `Синтетический текст до сбоя preflight ${randomUUID()}`;
  const edited = `Отредактированный синтетический текст после preflight ${randomUUID()}`;
  const runtimePath = `/users/assessment/cycles/${state.p3_a_previews.long.cycle_id}/runtime`;
  const posts = []; let armed = false, failedReads = 0;
  page.on('request', (request) => {
    if (request.method() === 'POST' && /\/m5\/situations\/[^/]+\/turns$/.test(new URL(request.url()).pathname)) {
      posts.push(request.postDataJSON());
    }
  });
  await page.route('**' + runtimePath, (route) => {
    if (armed && route.request().method() === 'GET') {
      armed = false; failedReads += 1; return route.abort('failed');
    }
    return route.continue();
  });
  await input.fill(initial); await submit.scrollIntoViewIfNeeded();
  // Arm immediately after a completed periodic read, leaving a full 1200ms
  // polling interval for this click's preflight. Bootstrap is already complete.
  await page.waitForResponse((response) => new URL(response.url()).pathname === runtimePath
    && response.request().method() === 'GET' && response.ok());
  armed = true; await submit.click();
  await expect.poll(() => failedReads).toBe(1);
  await expect(submit).toBeEnabled(); await expect(input).toBeEnabled(); await expect(input).toHaveValue(initial);
  expect(posts).toHaveLength(0);
  await input.fill(edited);
  const sent = page.waitForResponse((response) => /\/m5\/situations\/[^/]+\/turns$/.test(new URL(response.url()).pathname)
    && response.request().method() === 'POST');
  await submit.click(); expect((await sent).ok()).toBe(true);
  await expect.poll(async () => (await runtime(page)).trace.turns.filter((turn) => turn.content_text === edited).length).toBe(1);
  expect((await runtime(page)).trace.turns.filter((turn) => turn.content_text === initial)).toHaveLength(0);
  expect(posts).toHaveLength(1); expect(posts[0].content).toBe(edited);
  await expect(input).toHaveValue('');
  fs.writeFileSync(path.join(evidence, 'sender-preflight-zero-post.json'), JSON.stringify({
    first_preflight_transport_failures: failedReads, original_text_posts: 0, original_text_turns: 0,
    edited_text_posts: posts.length, edited_text_turns: 1, edited_payload: posts[0],
  }, null, 2) + '\n');
  await capture(page, 'sender-preflight-edited-draft-sent');
});

test('P3-AC03 late delivery from another Cycle and actor cannot overwrite the new draft or focus', async ({ page }) => {
  await open(page, 'delayed');
  const oldAnswer = `Синтетический старый ответ с задержкой ${randomUUID()}`;
  const submitted = page.waitForRequest((request) => /\/m5\/situations\/[^/]+\/turns$/.test(new URL(request.url()).pathname)
    && request.method() === 'POST');
  await page.locator('#interview-textarea').fill(oldAnswer); await page.locator('#interview-submit-button').click();
  const oldRequest = await submitted;
  await expect.poll(async () => (await runtime(page)).trace.turns.filter((turn) => turn.content_text === oldAnswer).length).toBe(1);
  // Real logout and password login in the SAME document leave the old fetch alive.
  // The seeded verified .test account takes password mode and sends no email.
  await page.locator('#interview-exit-button').click();
  await expect(page.locator('#interview-exit-button')).not.toHaveAttribute('aria-busy', 'true');
  await expect(page.locator('#email-input')).toBeVisible();
  await page.locator('#email-input').fill('other@example.test');
  await page.locator('#request-magic-link-button').click();
  await expect(page.locator('#auth-token-form')).toBeVisible();
  await page.locator('#magic-token-input').fill(state.password);
  await page.locator('#verify-magic-link-button').click();
  const confirm = page.getByRole('button', { name: 'Продолжить', exact: true }).filter({ visible: true });
  await expect(page.locator('#interview-panel').or(confirm).first()).toBeVisible();
  if (await confirm.isVisible()) await confirm.click();
  await expect(page.locator('#interview-panel')).toBeVisible();
  const input = page.locator('#interview-textarea'); await expect(input).toBeEnabled();
  const newDraft = 'Новый черновик другого Cycle/AS после смены синтетического участника.';
  await input.fill(newDraft); await input.focus();
  const oldResponse = await Promise.race([oldRequest.response(), new Promise((resolve) => setTimeout(() => resolve(null), 7000))]);
  await expect(input).toHaveValue(newDraft); await expect(input).toBeFocused();
  await expect(page.locator('.interview-message.own').filter({ hasText: oldAnswer })).toHaveCount(0);
  await expect(page.locator('#interview-error')).toBeHidden();
  const current = await runtime(page, 'short');
  expect(current.cycle_id).toBe(state.p3_a_previews.short.cycle_id);
  expect(current.current_situation.assessment_situation_id).toBe(state.p3_a_previews.short.assessment_situation_id);
  fs.writeFileSync(path.join(evidence, 'late-delivery-scope.json'), JSON.stringify({
    old_cycle: state.p3_a_previews.long.cycle_id, new_cycle: current.cycle_id,
    old_response_status: oldResponse?.status() ?? 'cancelled_or_no_response',
    new_draft_preserved: true, new_focus_preserved: true, old_turn_in_new_scope: false,
  }, null, 2) + '\n');
  await capture(page, 'late-delivery-new-scope');
});
