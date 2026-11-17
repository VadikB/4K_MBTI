// Actual bundled UI + synthetic HTTP and controlled clock, no DB/provider/mail.
import { test, expect } from '@playwright/test';
import http from 'node:http';
import fs from 'node:fs/promises';
import path from 'node:path';
import { draftSlot } from '../../web/js/answer-drafts.js';

let server, base;
const evidence = process.env.POSTW05_EVIDENCE || 'docs/evc/tasks/p4k-postw02-05/evidence/browser';
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

async function fixture(page, shared = null) {
  page.on('dialog', (dialog) => dialog.accept());
  const user = { id: 8, email: 'synthetic@example.test', full_name: 'Участник' };
  const initialModel = { cycle_id: 'synthetic-cycle',
    participant_progress: { planned_total: 8, current_position_no: 3, last_completed_position_no: 2 },
    status: { collection_status: 'active', remaining_seconds: 7200, deadline: '2026-11-20T12:00:00Z' },
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
  const run = shared || { model: initialModel, drafts: {}, calls: [], unexpected: [], offline: false, returning: false, rejectAnswer: false };
  const model = run.model;
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
      if (run.draftOffline) return route.abort('failed');
      const slot = draftSlot(model);
      const saved = run.drafts[slot] ||= { version: 0, revision: '', text: '' };
      if (req.method() === 'PUT') {
        const data = req.postDataJSON();
        if (data.slot_id !== slot || data.expected_version !== saved.version) return json({detail:'DRAFT_VERSION_CONFLICT'}, 409);
        Object.assign(saved, { text: data.text, revision: data.revision, version: saved.version + 1 });
      }
      return json({ ...saved, owner_id: '8', cycle_id: model.cycle_id, assessment_situation_id: 'synthetic-as',
        slot_id: slot, expires_at: '2026-11-20T12:00:00Z' });
    }
    if (url.endsWith('/draft/accepted')) return json({ status: 'accepted' });
    if (url.endsWith('/answer-status')) {
      const query = new URL(req.url()).searchParams;
      return json({ cycle_id: model.cycle_id, assessment_situation_id: 'synthetic-as',
        request_id: query.get('request_id'), turn_id: query.get('turn_id'), clarification_id: null,
        status: run.receipt ? 'accepted' : 'absent', processing_status: run.receipt ? 'applied' : null,
        turn: run.receipt || null });
    }
    if (url.endsWith('/turns') && req.method() === 'POST') {
      const data = req.postDataJSON();
      run.receipt = { turn_id: data.turn_id, request_id: data.request_id,
        content_text: data.content, speaker_type: 'assessee', sequence_no: 10 };
      model.trace.turns.push(run.receipt);
      if (run.dropAnswer) return route.abort('failed');
      return json({ turn: run.receipt });
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

for (const width of [1440, 390]) test(`05A/B/C/D/F durable draft browser ${width}`, async ({ page, context, browser }) => {
  await page.setViewportSize({ width, height: width === 1440 ? 1000 : 844 });
  await page.clock.install({ time: new Date('2026-11-17T12:00:00Z') });
  const errors = []; page.on('pageerror', e => errors.push(e.message));
  const run = await fixture(page);
  await page.goto(`${base}/?screen=interview`);
  const field = page.locator('#interview-textarea'), status = page.locator('#interview-draft-status');
  await expect(field).toBeEnabled();
  const raw = '  Черновик ответа\nВторая строка\n  ';
  await field.fill(raw); await page.clock.runFor(800);
  await expect(status).toHaveText('Черновик сохранён');
  expect(run.model.trace.turns).toHaveLength(2);
  await page.screenshot({ path: path.join(evidence, `saved-${width}.png`), fullPage: true });

  // A completely separate browser context has only the server revision.
  const clean = await browser.newContext({ viewport: { width, height: 844 } });
  const cleanPage = await clean.newPage(); await fixture(cleanPage, run);
  await cleanPage.goto(`${base}/?screen=interview`);
  await expect(cleanPage.locator('#interview-textarea')).toHaveValue(raw);
  await expect(cleanPage.locator('#interview-draft-status')).toContainText('Ответ ещё не отправлен');
  await clean.close();

  // Close the actual tab before the debounce; new tab in the same browser
  // receives the raw durable local buffer and then synchronizes it.
  const latest = raw + 'Сразу перед закрытием';
  await field.fill(latest); await page.close();
  const next = await context.newPage(); await next.setViewportSize({ width, height: width === 1440 ? 1000 : 844 });
  await next.clock.install({ time: new Date('2026-11-17T12:00:01Z') });
  await fixture(next, run); await next.goto(`${base}/?screen=interview`);
  await expect(next.locator('#interview-textarea')).toHaveValue(latest);
  await expect(next.locator('#interview-draft-status')).toHaveText('Черновик сохранён');

  run.draftOffline = true;
  await next.locator('#interview-textarea').fill(latest + '\nБез связи'); await next.clock.runFor(800);
  await expect(next.locator('#interview-draft-status')).toContainText('на этом устройстве');
  await next.screenshot({ path: path.join(evidence, `offline-${width}.png`), fullPage: true });
  run.draftOffline = false; await next.evaluate(() => window.dispatchEvent(new Event('online')));
  await expect(next.locator('#interview-draft-status')).toHaveText('Черновик сохранён');

  // Server change from another device creates an explicit conflict.
  const saved = run.drafts[draftSlot(run.model)]; saved.version++; saved.revision = 'other-device'; saved.text = 'Другая редакция';
  await next.locator('#interview-textarea').fill('Мой текст при конфликте'); await next.clock.runFor(800);
  await expect(next.locator('#interview-draft-status')).toContainText('другой вкладке');
  await expect(next.locator('#interview-textarea')).toHaveValue('Мой текст при конфликте');
  await next.screenshot({ path: path.join(evidence, `conflict-${width}.png`), fullPage: true });
  await next.getByRole('button', { name: 'Сохранить мой текст', exact: true }).click();
  await expect(next.locator('#interview-draft-status')).toHaveText('Черновик сохранён');

  // A real second tab uses the shared durable buffer; the first keeps its text
  // and requires an explicit choice when it receives the storage event.
  const sibling = await context.newPage(); await fixture(sibling, run);
  await sibling.goto(`${base}/?screen=interview`);
  await expect(sibling.locator('#interview-textarea')).toHaveValue('Мой текст при конфликте');
  await sibling.locator('#interview-textarea').fill('Редакция из второй вкладки');
  await expect(next.locator('#interview-draft-status')).toContainText('другой вкладке');
  await expect(next.locator('#interview-textarea')).toHaveValue('Мой текст при конфликте');
  await sibling.close();
  await next.getByRole('button', { name: 'Сохранить мой текст', exact: true }).click();
  await expect(next.locator('#interview-draft-status')).toHaveText('Черновик сохранён');

  // Lost accepted response + tab close retains the original request/Turn ID.
  run.dropAnswer = true;
  await next.locator('#interview-submit-button').click();
  await expect.poll(() => Boolean(run.receipt)).toBe(true);
  await next.close();
  const recovered = await context.newPage(); await recovered.setViewportSize({ width, height: width === 1440 ? 1000 : 844 });
  await fixture(recovered, run);
  await recovered.goto(`${base}/?screen=interview`);
  await expect(recovered.locator('#interview-textarea')).toHaveValue('');
  await expect.poll(() => run.calls.filter(c => c.url.endsWith('/answer-status')).length).toBeGreaterThan(0);
  expect(run.calls.filter(c => c.url.endsWith('/turns') && c.method === 'POST')).toHaveLength(1);
  expect(run.unexpected).toEqual([]); expect(errors).toEqual([]);
  const geometry = await recovered.evaluate(() => ({ width: innerWidth, scrollWidth: document.documentElement.scrollWidth }));
  expect(geometry.scrollWidth).toBeLessThanOrEqual(width);
  await fs.writeFile(path.join(evidence, `receipt-${width}.json`), JSON.stringify({ geometry, turns: run.model.trace.turns.length,
    posts: run.calls.filter(c => c.url.endsWith('/turns') && c.method === 'POST').length, errors }));
});
