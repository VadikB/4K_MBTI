import { test, expect } from '@playwright/test';
import http from 'node:http';
import fs from 'node:fs/promises';
import path from 'node:path';

// Component evidence: actual built app/native Chromium, synthetic HTTP inputs.
// Real HTTP/PostgreSQL/Continue are independently covered by p3-a-r1-return.
let server, base;
test.beforeAll(async () => {
  server = http.createServer(async (request, response) => {
    try {
      const pathname = new URL(request.url, 'http://127.0.0.1').pathname;
      const filename = path.join(process.cwd(), pathname === '/' ? 'web/index.html' : pathname);
      response.setHeader('Content-Type', ({ '.js': 'application/javascript', '.css': 'text/css', '.html': 'text/html', '.svg': 'image/svg+xml' })[path.extname(filename)] || 'application/octet-stream');
      response.end(await fs.readFile(filename));
    } catch { response.statusCode = 404; response.end('missing'); }
  });
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  base = `http://127.0.0.1:${server.address().port}`;
});
test.afterAll(async () => { if (server) await new Promise((resolve) => server.close(resolve)); });

async function fixture(page, total) {
  const user = { id: 8, email: 'synthetic@example.test', full_name: 'Synthetic participant' };
  const model = { runtime_kind: 'cycle', cycle_id: 'remain06-cycle', return_policy_enabled: false,
    status: { collection_status: 'active', remaining_seconds: 123 },
    plan: { catalog: Array.from({ length: 9 }), route: Array.from({ length: total }) },
    route: { positions: [{ position_no: 1, state: 'in_progress', current_assessment_situation_id: 'remain06-as' }],
      progress: { total_positions: total, completed_positions: 0 } },
    current_situation: { assessment_situation_id: 'remain06-as', status: 'active', participant_payload: {
      title: 'Синтетическая ситуация REMAIN06', situation: 'Исходные сведения. '.repeat(100),
      assessee_task: 'Опишите следующий шаг.', initial_materials: [{ material_id: 'M1', title: 'Материал', text: 'Разрешённые сведения' }],
    } }, trace: { turns: [], events: [] } };
  let release;
  let held = true, failed = false, reads = 0;
  const gate = new Promise((resolve) => { release = resolve; });
  const json = (route, body, status = 200) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) });
  await page.route('**/users/**', async (route) => {
    const pathname = new URL(route.request().url()).pathname;
    if (pathname === '/users/session/restore') return json(route, { authenticated: true, user, is_admin: false, dashboard: {} });
    if (pathname === '/users/8/session-bootstrap') return json(route, { user, is_admin: false, dashboard: {} });
    if (pathname === '/users/8/journey-state') return json(route, { next_action: 'resume_assessment',
      assessment: { runtime_kind: 'cycle', cycle_id: model.cycle_id, assessment_situation_id: 'remain06-as', status: 'active' },
      profile: { status: 'complete' }, onboarding: { status: 'completed' } });
    if (pathname.endsWith('/return-state')) return json(route, { detail: 'M7_RETURN_POLICY_NOT_SNAPSHOTTED' }, 409);
    if (pathname.endsWith('/runtime')) {
      reads++;
      if (held) await gate;
      return failed ? route.abort('failed') : json(route, model);
    }
    if (pathname === '/users/version') return json(route, { version: 'remain06-controlled' });
    return json(route, {}, 404);
  });
  await page.addInitScript(() => localStorage.setItem('agent4k.assessmentTotalCases', '5'));
  return { model, release: () => { held = false; release(); }, fail: (value) => { failed = value; }, reads: () => reads };
}

for (const total of [8, 3]) test(`F18/F19 pending, plan${total}, network recovery and zero versus unknown`, async ({ page }, info) => {
  const f = await fixture(page, total);
  try {
    await page.goto(`${base}/?screen=interview`);
    await expect(page.locator('#interview-panel')).toBeVisible();
    await expect(page.locator('#interview-case-badge')).toHaveText('Прогресс уточняется');
    await expect(page.locator('#interview-timer-badge')).toHaveText('Время уточняется');
    await expect(page.locator('#interview-textarea')).toBeDisabled();
    await page.screenshot({ path: info.outputPath('pending.png') });
    f.release();
    await expect(page.locator('#interview-case-badge')).toHaveText(`Ситуация 1 из ${total}\nЗавершено 0 из ${total}`);
    await expect(page.locator('#interview-timer-badge')).toHaveText('02:03');
    f.fail(true);
    await expect(page.locator('#interview-timer-badge')).toHaveText('Время уточняется');
    await expect(page.locator('#interview-timer-badge')).not.toHaveClass(/is-paused/);
    f.fail(false); f.model.status.remaining_seconds = 0;
    await expect(page.locator('#interview-timer-badge')).toHaveText('00:00');
    f.model.status.remaining_seconds = null;
    await expect(page.locator('#interview-timer-badge')).toHaveText('Время уточняется');
    await page.reload();
    await expect(page.locator('#interview-case-badge')).toHaveText(`Ситуация 1 из ${total}\nЗавершено 0 из ${total}`);
    await expect(page.locator('#interview-timer-badge')).toHaveText('Время уточняется');
    expect(f.reads()).toBeLessThanOrEqual(12);
    await page.screenshot({ path: info.outputPath('recovered.png') });
  } finally { f.release(); }
});

test('F21 native shortcuts, own text/IME, protected copy and synthetic beforeinput/paste/drop', async ({ page }, info) => {
  const f = await fixture(page, 8); f.release();
  await page.goto(`${base}/?screen=interview`);
  const input = page.locator('#interview-textarea');
  await expect(input).toBeEnabled();
  await input.pressSequentially('Свой текст');
  await input.press('ArrowLeft');
  const before = await input.evaluate((e) => ({ value: e.value, start: e.selectionStart, end: e.selectionEnd }));
  for (const shortcut of ['Control+v', 'Meta+v', 'Shift+Insert']) await input.press(shortcut);
  const transfers = await input.evaluate((e) => {
    const events = [new ClipboardEvent('paste', { bubbles: true, cancelable: true }),
      new InputEvent('beforeinput', { inputType: 'insertFromPaste', data: 'external', bubbles: true, cancelable: true }),
      new InputEvent('beforeinput', { inputType: 'insertFromDrop', data: 'own', bubbles: true, cancelable: true }),
      new DragEvent('drop', { bubbles: true, cancelable: true })];
    return events.map((event) => { e.dispatchEvent(event); return event.defaultPrevented; });
  });
  expect(transfers).toEqual([true, true, true, true]);
  expect(await input.evaluate((e) => ({ value: e.value, start: e.selectionStart, end: e.selectionEnd }))).toEqual(before);
  const cdp = await page.context().newCDPSession(page);
  try {
    await cdp.send('Input.imeSetComposition', { text: 'あ', selectionStart: 1, selectionEnd: 1 });
    await cdp.send('Input.insertText', { text: 'あ' });
    await expect(input).toHaveValue(/あ/);
  } finally { await cdp.detach(); }
  const result = await page.evaluate(() => {
    const error = document.querySelector('#interview-error'); error.textContent = 'Реальная ошибка'; error.hidden = false;
    const protectedNode = document.querySelector('.interview-message--situation');
    document.activeElement.blur();
    const selection = getSelection(), range = document.createRange(); range.selectNode(protectedNode);
    selection.removeAllRanges(); selection.addRange(range);
    const selectionText = selection.toString();
    const blocked = ['copy', 'cut'].map((type) => {
      const event = new ClipboardEvent(type, { bubbles: true, cancelable: true }); protectedNode.dispatchEvent(event); return event.defaultPrevented;
    });
    const protectedActions = ['contextmenu', 'dragstart'].map((type) => {
      const event = new Event(type, { bubbles: true, cancelable: true });
      protectedNode.dispatchEvent(event); return event.defaultPrevented;
    });
    selection.removeAllRanges();
    const own = document.querySelector('#interview-textarea'); own.focus(); own.select();
    const allowed = new ClipboardEvent('copy', { bubbles: true, cancelable: true }); own.dispatchEvent(allowed);
    return { blocked, selectionText, protectedActions, ownAllowed: !allowed.defaultPrevented, error: error.textContent };
  });
  // Chromium user-select:none may exclude protected content before a copy event
  // reaches the fallback handler. Handler execution is separately proven in VM.
  expect(result.blocked.every(Boolean) || result.selectionText === '', JSON.stringify(result)).toBe(true);
  expect(result.ownAllowed).toBe(true); expect(result.error).toBe('Реальная ошибка');
  expect(result.protectedActions).toEqual([true, true]);
  await fs.writeFile(info.outputPath('protected-selection.json'), JSON.stringify(result, null, 2));
  await input.press('Control+c');
  await page.screenshot({ path: info.outputPath('clipboard-and-ime.png') });
  info.annotations.push({ type: 'scope', description: 'Native keyboard + Chromium CDP IME; paste/drop/copy events synthetic. No clipboard read/clear, physical devices and OS context menu NOT_RUN.' });
});
