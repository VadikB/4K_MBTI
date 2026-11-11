import { test, expect } from '@playwright/test';
import { createServer } from 'node:http';
import fs from 'node:fs';
import path from 'node:path';

// Real Chromium, production source modules/DOM/CSS and handlers. Transport faults
// are injected; this suite does not claim a server commit or PostgreSQL receipt.
const root = process.cwd();
const evidence = process.env.REMARKS02_CHAT_EVIDENCE || path.join(root, '.test-stand/remarks02-chat');
let server, base;
test.beforeAll(async () => {
  fs.mkdirSync(evidence, { recursive: true });
  server = createServer((request, response) => {
    const pathname = new URL(request.url, 'http://localhost').pathname;
    const file = pathname === '/' ? path.join(root, 'web/index.html') : path.resolve(root, '.' + decodeURIComponent(pathname));
    if (!file.startsWith(root + path.sep) || !fs.existsSync(file) || !fs.statSync(file).isFile()) {
      response.writeHead(404); response.end(); return;
    }
    let content = fs.readFileSync(file);
    if (pathname === '/') content = content.toString().replace(/<script\b[^>]*>[\s\S]*?<\/script>/g, '');
    response.setHeader('Content-Type', file.endsWith('.js') ? 'text/javascript'
      : file.endsWith('.css') ? 'text/css' : file.endsWith('.html') ? 'text/html' : 'application/octet-stream');
    response.end(content);
  });
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  base = `http://127.0.0.1:${server.address().port}`;
});
test.afterAll(async () => { if (server) await new Promise((resolve) => server.close(resolve)); });

const snapshot = () => ({
  cycle_id: 'remarks02-cycle-a',
  current_situation: { assessment_situation_id: 'remarks02-as-a', status: 'active',
    participant_payload: { title: 'Синтетическая ситуация проверки ошибок', initial_materials: [] } },
  route: { positions: [] }, status: { collection_status: 'active', remaining_seconds: 7200 },
  trace: { turns: [{ turn_id: 'previous-owned-turn', speaker_type: 'assessee', content_text: 'Сохранённый тестовый ответ.', sequence_no: 1 }], events: [] },
});
const boot = async (page, intercept = async () => false) => {
  const pageErrors = [];
  page.on('pageerror', (error) => pageErrors.push(error.message));
  await page.route('**/users/**', async (route) => {
    if (await intercept(route)) return;
    const pathname = new URL(route.request().url()).pathname;
    if (pathname.endsWith('/return-state')) {
      return route.fulfill({ json: { cycle_id: 'remarks02-cycle-a', allowed_action: 'none' } });
    }
    if (pathname.endsWith('/runtime')) return route.fulfill({ json: snapshot() });
    if (pathname.endsWith('/presence')) return route.fulfill({ json: { heartbeat_interval_seconds: 60 } });
    return route.fulfill({ status: 404, json: { detail: 'Synthetic transport route not configured' } });
  });
  await page.goto(base);
  await page.evaluate(async () => {
    const { state } = await import('/web/js/state.js');
    const { loadInterview } = await import('/web/js/screen-loaders.js');
    const { initWiring } = await import('/web/js/wiring.js');
    initWiring();
    Object.assign(state, { pendingUser: { id: 888, email: 'owned-remarks02@example.invalid' }, identityEpoch: 1,
      assessmentRuntimeKind: 'cycle', productCycleId: 'remarks02-cycle-a', productAssessmentSituationId: 'remarks02-as-a' });
    const interview = await import('/web/js/screens/interview.js');
    await loadInterview();
    window.__remarks02 = { state, interview };
    interview.openInterview();
  });
  await expect(page.locator('.interview-message--situation')).toHaveCount(1);
  await expect(page.locator('#interview-submit-button')).toBeEnabled();
  page.on('dialog', (dialog) => dialog.accept());
  return pageErrors;
};

test('F07 browser actual Pause/Finish/Additional show safe network and precise business refusals', async ({ page }) => {
  let mode = 'network';
  const errors = await boot(page, async (route) => {
    if (route.request().method() !== 'POST') return false;
    if (mode === 'network') await route.abort('failed');
    else await route.fulfill({ status: 403, json: { detail: 'ASSIGNMENT_CANCELLED' } });
    return true;
  });
  for (const id of ['interview-pause-button', 'interview-finish-button', 'interview-additional-button']) {
    mode = 'network'; await page.locator('#' + id).click();
    await expect(page.locator('#interview-error')).toContainText('Проверьте соединение');
    await expect(page.locator('#interview-error')).not.toContainText('Failed to fetch');
    mode = 'business'; await page.locator('#' + id).click();
    await expect(page.locator('#interview-error')).toContainText('отменено администратором');
  }
  expect(errors).toEqual([]);
  fs.writeFileSync(path.join(evidence, 'handler-errors.json'), JSON.stringify({ pageErrors: errors, actions: 3, transportAndBusiness: 'PASS' }, null, 2));
});

test('F08 browser unknown send retains recovery through background faults and storage failures are honest', async ({ page }) => {
  let backgroundFailure = false;
  const errors = await boot(page, async (route) => {
    if (route.request().method() === 'POST' && route.request().url().endsWith('/turns')) {
      backgroundFailure = true; await route.abort('failed'); return true;
    }
    if (backgroundFailure) { await route.abort('failed'); return true; }
    return false;
  });
  const input = page.locator('#interview-textarea');
  await input.fill('Собственный текст перед неизвестным исходом отправки.');
  await page.locator('#interview-submit-button').click();
  await expect(page.locator('#interview-error')).toContainText('исход отправки');
  await expect(page.locator('.interview-message-retry:visible')).toHaveText('Проверить и повторить');
  const pendingBefore = await page.evaluate(() => Object.keys(sessionStorage)
    .filter((key) => key.startsWith('agent4k.assessmentPending:')).map((key) => sessionStorage.getItem(key)));
  await expect(page.locator('#interview-submit-button')).toBeDisabled();
  await expect(page.locator('#interview-finish-button')).toBeDisabled();
  await page.waitForTimeout(1400); // one real polling interval fails
  await expect(page.locator('#interview-error')).toContainText('исход отправки');
  await expect(page.locator('#interview-error')).not.toContainText('Введённый текст сохранён');
  await expect(page.locator('.interview-message-retry:visible')).toHaveCount(1);
  const pendingAfter = await page.evaluate(() => Object.keys(sessionStorage)
    .filter((key) => key.startsWith('agent4k.assessmentPending:')).map((key) => sessionStorage.getItem(key)));
  expect(pendingAfter).toEqual(pendingBefore);
  for (const width of [1440, 390, 320]) {
    await page.setViewportSize({ width, height: 900 });
    await page.locator('.interview-message-retry:visible').scrollIntoViewIfNeeded();
    await expect(page.locator('.interview-message-retry:visible')).toBeInViewport();
    await page.screenshot({ path: path.join(evidence, `unknown-recovery-${width}.png`), fullPage: true });
  }
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.evaluate(() => { document.body.style.zoom = '2'; });
  await page.locator('.interview-message-retry:visible').scrollIntoViewIfNeeded();
  await expect(page.locator('.interview-message-retry:visible')).toBeInViewport();
  await page.screenshot({ path: path.join(evidence, 'unknown-recovery-css-zoom200.png'), fullPage: true });
  expect(errors).toEqual([]);

  // New page scope, old saved revision then current storage write failure.
  backgroundFailure = false;
  await page.reload();
  await page.evaluate(() => sessionStorage.clear());
  await page.unroute('**/users/**');
  await boot(page);
  await input.fill('Прежний сохранённый черновик');
  await page.evaluate(() => {
    Storage.prototype.setItem = function () { throw new DOMException('Synthetic quota exceeded', 'QuotaExceededError'); };
  });
  await input.fill('Новая редакция при отказе storage');
  await expect(page.locator('#interview-error')).toContainText('Не удалось сохранить текущий текст');
  await page.route('**/users/assessment/**', (route) => route.abort('failed'));
  await page.evaluate(() => window.__remarks02.interview.loadProductRuntime().catch(window.__remarks02.interview.showInterviewRuntimeError));
  await expect(page.locator('#interview-error')).toContainText('Сохранение введённого текста не подтверждено');
  await expect(input).toHaveValue('Новая редакция при отказе storage');
  await expect(page.locator('#interview-error')).not.toContainText('Введённый текст сохранён');
  await page.screenshot({ path: path.join(evidence, 'storage-failure.png'), fullPage: true });
});

test('F09 browser deferred rejected poll and action preserve a new identity/Cycle/AS error and draft', async ({ page }) => {
  let held = false, enabled = false, release;
  let gate = new Promise((resolve) => { release = resolve; });
  const errors = await boot(page, async (route) => {
    if (enabled && !held && (route.request().url().endsWith('/return-state') || route.request().url().endsWith('/control'))) {
      held = true; await gate; await route.abort('failed'); return true;
    }
    return false;
  });
  for (const channel of ['poll', 'action', 'same-scope-action']) {
    held = false; enabled = true;
    gate = new Promise((resolve) => { release = resolve; });
    if (channel === 'poll') {
      await page.evaluate(() => {
        const { interview } = window.__remarks02;
        window.__remarks02.request = interview.loadProductRuntime().catch(interview.showInterviewRuntimeError);
      });
    } else await page.locator('#interview-pause-button').click();
    await expect.poll(() => held).toBe(true);
    await page.evaluate(async (channel) => {
      const { state } = window.__remarks02;
      if (channel === 'same-scope-action') {
        const { advanceAssessmentViewGeneration } = await import('/web/js/assessment-errors.js');
        state.currentScreen = 'home'; advanceAssessmentViewGeneration();
        state.currentScreen = 'interview'; advanceAssessmentViewGeneration();
      } else {
        state.pendingUser = { id: 999 }; state.identityEpoch += 1;
        state.productCycleId = 'remarks02-cycle-b'; state.productAssessmentSituationId = 'remarks02-as-b';
      }
      document.getElementById('interview-error').textContent = 'Сообщение новой оценки';
      const input = document.getElementById('interview-textarea'); input.value = 'Черновик новой оценки';
      input.dispatchEvent(new Event('input', { bubbles: true }));
    }, channel);
    enabled = false; release();
    await page.waitForTimeout(100);
    await expect(page.locator('#interview-error')).toHaveText('Сообщение новой оценки');
    await expect(page.locator('#interview-textarea')).toHaveValue('Черновик новой оценки');
    // Restore only synthetic fixture identity between the two fault channels.
    await page.evaluate(() => {
      const { state } = window.__remarks02;
      state.pendingUser = { id: 888 }; state.identityEpoch += 1;
      state.productCycleId = 'remarks02-cycle-a'; state.productAssessmentSituationId = 'remarks02-as-a';
    });
  }
  expect(errors).toEqual([]);
  fs.writeFileSync(path.join(evidence, 'stale-rejections.json'), JSON.stringify({ pageErrors: errors, channels: ['poll', 'action', 'same-scope-action'], result: 'PASS' }, null, 2));
});
