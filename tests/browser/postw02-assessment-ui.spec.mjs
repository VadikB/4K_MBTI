// Actual bundled UI + synthetic HTTP and controlled clock, no DB/provider/mail.
import { test, expect } from '@playwright/test';
import http from 'node:http';
import fs from 'node:fs/promises';
import path from 'node:path';
import { draftSlot } from '../../web/js/answer-drafts.js';

let server, base;
const evidence = process.env.POSTW02_UI_EVIDENCE || '.test-stand/postw02-ui';
const reference = process.env.POSTW02_REFERENCE;
test.beforeAll(async () => {
  await fs.mkdir(evidence, { recursive: true });
  server = http.createServer(async (req, res) => {
    try {
      const pathname = decodeURIComponent(new URL(req.url, 'http://localhost').pathname);
      const file = pathname.startsWith('/reference/') && reference
        ? path.join(reference, 'dist', pathname.slice('/reference/'.length))
        : path.join(process.cwd(), pathname === '/' ? 'web/index.html' : pathname);
      res.setHeader('Content-Type', { '.html': 'text/html', '.css': 'text/css', '.js': 'application/javascript',
        '.mjs': 'application/javascript', '.svg': 'image/svg+xml', '.woff': 'font/woff' }[path.extname(file)] || 'application/octet-stream');
      res.end(await fs.readFile(file));
    } catch { res.statusCode = 404; res.end('missing'); }
  });
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  base = `http://127.0.0.1:${server.address().port}`;
});
test.afterAll(async () => {
  const port = server?.address()?.port;
  if (server?.listening) await new Promise((resolve) => server.close(resolve));
  await fs.writeFile(path.join(evidence, 'cleanup.json'), JSON.stringify({ port, listening: server?.listening, db: null, llm: 0, mail: 0 }));
});

async function fixture(page) {
  page.on('dialog', (dialog) => dialog.accept());
  const user = { id: 8, email: 'synthetic@example.test', full_name: 'Участник' };
  const model = { cycle_id: 'synthetic-cycle',
    participant_progress: { planned_total: 8, current_position_no: 3, last_completed_position_no: 2 },
    status: { collection_status: 'active', remaining_seconds: 7200, calendar_deadline: '2026-11-20T12:00:00Z' },
    route: { positions: [{ position_no: 3, state: 'in_progress', current_assessment_situation_id: 'synthetic-as' }],
      progress: { total_positions: 8, completed_positions: null } },
    current_situation: { assessment_situation_id: 'synthetic-as', status: 'active', participant_payload: {
      title: 'Рабочая ситуация', introduction: 'Команда готовит запуск сервиса.',
      initial_situation: 'Клиенту нужно согласовать план. Собеседник предлагает обсудить доступные варианты.',
      assessee_task: 'Обсудите запрос и предложите следующий шаг.',
      initial_materials: [{ material_id: 'public-material', title: 'Доступные сведения', text: 'На проверку данных нужен один рабочий день.' }],
    } }, trace: { turns: [
      { turn_id: 'saved-question', sequence_no: 1, speaker_type: 'character', speaker_name: 'Собеседник', content_text: 'Какие шаги вы предложите?' },
      { turn_id: 'saved-answer', sequence_no: 2, speaker_type: 'assessee', content_text: 'Сначала уточню приоритеты, затем согласую план.' },
    ], events: [] } };
  const run = { model, calls: [], unexpected: [], offline: false, returning: false, rejectAnswer: false };
  await page.route('**/users/**', async (route) => {
    const req = route.request(), url = new URL(req.url()).pathname;
    run.calls.push({ url, method: req.method(), body: req.postDataJSON() });
    const json = (body, status = 200) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) });
    if (url === '/users/version') return json({ version: '2.1.14' });
    if (url === '/users/session/restore') return json({ authenticated: true, user, dashboard: {} });
    if (url === '/users/8/session-bootstrap') return json({ user, dashboard: {} });
    if (url === '/users/8/journey-state') return json({ next_action: 'resume_assessment',
      assessment: { runtime_kind: 'cycle', cycle_id: model.cycle_id, assessment_situation_id: 'synthetic-as', status: 'active' },
      profile: { status: 'complete' }, onboarding: { status: 'completed' } });
    if (url.endsWith('/return-state')) return json(run.returning ? {
      cycle_id: model.cycle_id, current_assessment_situation_id: 'synthetic-as', current_assessment_situation_status: 'scenario_ended',
      position_no: 3, participant_progress: model.participant_progress,
      collection_status: 'active', allowed_action: 'continue_current', remaining_seconds: 7200,
      progress: { total_positions: 8 },
    } : { cycle_id: model.cycle_id, allowed_action: 'connected' });
    if (url.endsWith('/draft')) {
      const slot = draftSlot(model); run.drafts ||= {};
      const saved = run.drafts[slot] ||= { version: 0, revision: '', text: '' };
      if (req.method() === 'PUT') {
        const data = req.postDataJSON();
        if (data.expected_version !== saved.version) return json({ detail: 'DRAFT_VERSION_CONFLICT' }, 409);
        Object.assign(saved, { version: saved.version + 1, revision: data.revision, text: data.text });
      }
      return json({ ...saved, owner_id: '8', cycle_id: model.cycle_id, assessment_situation_id: 'synthetic-as',
        slot_id: slot, expires_at: '2026-11-20T12:00:00Z' });
    }
    if (url.endsWith('/runtime')) return run.offline ? route.abort('failed') : json(model);
    if (url.endsWith('/transitions')) {
      model.current_situation.status = 'scenario_ended'; model.blocking_system_wait = true;
      model.finish_availability = { allowed: false, reason: 'ANALYSIS_PENDING' }; model.pipeline = { status: 'running' };
      return json({ status: 'scenario_ended' });
    }
    if (url.endsWith('/return-continue')) {
      run.returning = false;
      return json({ status: 'continued', assessment_situation_id: 'synthetic-as' });
    }
    if (url.endsWith('/presence')) return json({ heartbeat_interval_seconds: 10 });
    if (url.endsWith('/turns') && req.method() === 'POST' && run.rejectAnswer) return route.abort('failed');
    if (url.includes('/turns/') && url.endsWith('/outcome')) return json({ status: 'absent' });
    // Cabinet navigation is read-only; production dashboard may request history.
    if (url === '/users/8/assessment-cycle-history') return json({ cycles: [], reports: [] });
    run.unexpected.push(url);
    return json({ detail: `Unexpected ${url}` }, 500);
  });
  return run;
}
async function screenshot(page, scene, width) {
  await page.evaluate(() => document.fonts.ready);
  const geometry = await page.evaluate(() => {
    const rect = (s) => { const r = document.querySelector(s)?.getBoundingClientRect(); return r ? { x: r.x, y: r.y, width: r.width, height: r.height, bottom: r.bottom } : null; };
    const input = rect('#interview-form'), error = document.querySelector('#interview-error');
    return { viewport: innerWidth, scrollWidth: document.documentElement.scrollWidth,
      input, messages: rect('.interview-messages-shell'),
      font: getComputedStyle(document.querySelector('#interview-textarea')).fontFamily,
      feedbackColor: getComputedStyle(error).color,
      visibleControls: [...document.querySelectorAll('#interview-panel button')].filter((b) => b.getClientRects().length).map((b) => b.textContent.trim()) };
  });
  expect(geometry.scrollWidth).toBeLessThanOrEqual(width);
  expect(geometry.visibleControls).not.toContain('Пауза');
  expect(geometry.visibleControls).not.toContain('Прервать и продолжить позже');
  expect(geometry.font).toContain('Onest');
  await fs.writeFile(path.join(evidence, `${scene}-${width}.json`), JSON.stringify(geometry, null, 2));
  await page.screenshot({ path: path.join(evidence, `${scene}-${width}.png`), fullPage: true });
}

for (const width of [1440, 390]) test(`chat, clarification, bounded waiting, return, break ${width}`, async ({ page, context }) => {
  await page.setViewportSize({ width, height: width === 1440 ? 1000 : 844 });
  await page.clock.install({ time: new Date('2026-11-16T12:00:00Z') });
  const errors = []; page.on('pageerror', (e) => errors.push(e.message));
  const run = await fixture(page);
  await page.goto(`${base}/?screen=interview`);
  await expect(page.locator('#interview-case-badge')).toHaveText('3 ситуация из 8');
  await expect(page.locator('.interview-message--situation')).toHaveCount(1);
  await expect(page.locator('#interview-pause-button')).toBeHidden();
  await expect(page.locator('#interview-additional-button')).toBeHidden();
  await expect(page.locator('#interview-finish-button')).toBeEnabled();
  const area = page.locator('#interview-scroll-area');
  await expect(page.locator('.product-situation-title')).toBeVisible();
  await area.focus(); await page.keyboard.press('End');
  await page.locator('#interview-textarea').focus();
  await page.keyboard.press('Tab');
  await expect(page.locator('#interview-submit-button')).toBeFocused();
  const form = await page.locator('#interview-form').boundingBox();
  const finish = await page.locator('#interview-finish-button').boundingBox();
  expect(finish.y).toBeGreaterThanOrEqual(form.y + form.height);
  await screenshot(page, 'active', width);
  run.model.current_situation.participant_payload.introduction = 'Команда готовит запуск сервиса. '.repeat(65);
  await page.clock.fastForward(1500);
  await expect.poll(() => area.evaluate((n) => n.scrollHeight > n.clientHeight)).toBe(true);
  await area.focus(); await page.keyboard.press('End');
  await page.locator('#interview-textarea').fill('Собственный длинный текст. '.repeat(120));
  const inputRect = await page.locator('#interview-form').boundingBox();
  const messageRect = await page.locator('.interview-messages-shell').boundingBox();
  expect(inputRect.y).toBeGreaterThanOrEqual(messageRect.y + messageRect.height);
  await screenshot(page, 'long', width);
  await page.locator('#interview-textarea').fill('');
  await page.locator('#interview-finish-button').click();
  await expect(page.locator('#interview-error')).toContainText('Ожидайте завершения обработки');
  await page.clock.fastForward(46000);
  await expect(page.locator('#interview-error')).toHaveAttribute('data-tone', 'neutral');
  await expect(page.locator('#interview-finish-button')).toBeDisabled();
  const posts = () => run.calls.filter((c) => c.method === 'POST' && !c.url.endsWith('/presence'));
  expect(posts()).toHaveLength(1);
  await screenshot(page, 'waiting', width);
  const readsBefore = run.calls.length;
  await page.clock.fastForward(60000);
  expect(run.calls).toHaveLength(readsBefore);
  await page.getByRole('button', { name: 'Проверить состояние', exact: true }).click();
  await expect(page.locator('#interview-error')).toContainText('Обработка занимает больше времени');
  expect(posts()).toHaveLength(1);
  run.offline = true;
  await page.getByRole('button', { name: 'Проверить состояние', exact: true }).click();
  await expect(page.locator('#interview-error')).toContainText('Не удалось обновить состояние');
  await screenshot(page, 'offline', width);
  run.offline = false;
  run.model.pipeline.status = 'failed';
  await page.getByRole('button', { name: 'Проверить состояние', exact: true }).click();
  await expect(page.locator('#interview-error')).toHaveAttribute('data-tone', 'failed');
  run.model.pipeline.status = 'running'; run.model.blocking_system_wait = false;
  run.model.clarification = { id: 'saved-clarification', status: 'ASK', question_turn_id: 'clarification-turn', question: { text: 'Почему вы выбрали такой порядок?' } };
  await page.getByRole('button', { name: 'Проверить состояние', exact: true }).click();
  await expect(page.locator('#interview-textarea')).toBeEnabled();
  await expect(page.locator('#interview-finish-button')).toBeDisabled();
  await screenshot(page, 'clarify', width);
  run.returning = true;
  await page.reload();
  await expect(page.getByRole('button', { name: 'Продолжить', exact: true })).toBeVisible();
  await expect(page.locator('#interview-form')).toBeHidden();
  await expect(page.locator('#interview-submit-button')).toBeDisabled();
  await screenshot(page, 'return', width);
  await page.getByRole('button', { name: 'Продолжить', exact: true }).click();
  await expect(page.locator('#interview-textarea')).toBeEnabled();
  await expect(page.locator('#interview-messages')).toContainText('Сначала уточню приоритеты');
  await expect(page.locator('#interview-messages')).toContainText('Почему вы выбрали такой порядок');
  expect(run.calls.some((c) => /equivalent|replacement|interrupt/.test(c.url + JSON.stringify(c.body)))).toBe(false);
  run.model.current_situation = null; run.model.between_situations = true;
  run.model.preparation_operation = { operation_id: 'next:synthetic-as', status: 'running' };
  run.model.participant_progress = { planned_total: 8, current_position_no: null, last_completed_position_no: 3 };
  await page.reload();
  await expect(page.getByRole('heading', { name: 'Ситуация 3 завершена' })).toBeVisible();
  await expect(page.locator('#interview-case-badge')).toBeHidden();
  await expect(page.getByRole('button', { name: 'Проверить состояние', exact: true })).toBeEnabled();
  await expect(page.getByRole('button', { name: 'Приступить к следующей ситуации' })).toHaveCount(0);
  await expect(page.locator('#interview-form')).toBeHidden();
  await screenshot(page, 'between', width);
  const beforeLeave = posts().length;
  await page.locator('#interview-profile-button').click();
  const afterLeaveReads = run.calls.filter((c) => c.url.endsWith('/runtime')).length;
  await page.clock.fastForward(60000);
  expect(run.calls.filter((c) => c.url.endsWith('/runtime'))).toHaveLength(afterLeaveReads);
  expect(posts()).toHaveLength(beforeLeave);
  expect(errors).toEqual([]);
  expect(run.unexpected).toEqual([]);
  await fs.writeFile(path.join(evidence, `requests-${width}.json`), JSON.stringify(run.calls, null, 2));
  if (reference) {
    const refPage = await context.newPage();
    await refPage.setViewportSize({ width, height: width === 1440 ? 1000 : 844 });
    for (const scene of ['active', 'waiting', 'clarify', 'return', 'between']) {
      await refPage.goto(`${base}/reference/screen.html?scene=assessment-${scene}`);
      await expect(refPage.locator('.assessment-main')).toBeVisible();
      await refPage.screenshot({ path: path.join(evidence, `reference-${scene}-${width}.png`), fullPage: true });
    }
    await refPage.close();
  }
});


test('unknown answer outcome keeps the draft; manual processing check never resends it', async ({ page }) => {
  await page.clock.install({ time: new Date('2026-11-16T12:00:00Z') });
  const run = await fixture(page);
  run.rejectAnswer = true;
  await page.goto(`${base}/?screen=interview`);
  await expect(page.locator('#interview-textarea')).toBeEnabled();
  const text = 'Мой собственный ответ, исход отправки которого неизвестен.';
  await page.locator('#interview-textarea').fill(text);
  await page.locator('#interview-submit-button').click();
  await expect(page.locator('#interview-textarea')).toHaveValue(text);
  await expect(page.locator('.interview-message-delivery-status').last()).toContainText(/не подтвержд|Проверить|исход/i);
  const sent = run.calls.filter((c) => c.method === 'POST' && c.url.endsWith('/turns'));
  expect(sent).toHaveLength(1);
  run.model.current_situation.status = 'scenario_ended';
  run.model.pipeline = { status: 'running' }; run.model.finish_availability = { allowed: false };
  await page.reload();
  await expect(page.locator('#interview-textarea')).toHaveValue(text);
  await expect(page.locator('#interview-error')).not.toContainText('Ответ сохранён');
  await page.getByRole('button', { name: 'Проверить сохранение', exact: true }).click();
  expect(run.calls.filter((c) => c.method === 'POST' && c.url.endsWith('/turns'))).toHaveLength(1);
});
