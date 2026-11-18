// Production bundle in Chromium with controlled HTTP/clock. One worker, no retries/LLM/mail/DB.
import { test, expect } from '@playwright/test';
import fs from 'node:fs/promises';
import http from 'node:http';
import path from 'node:path';
import { draftFixture, preparationModel } from './fixtures/postw02-qa.mjs';

const evidence = process.env.QA03_EVIDENCE || 'docs/evc/tasks/p4k-postw02-qa-03/evidence/browser';
let server, base;
test.beforeAll(async () => {
  await fs.mkdir(evidence, { recursive: true });
  server = http.createServer(async (req, res) => {
    try {
      const pathname = new URL(req.url, 'http://localhost').pathname;
      const file = path.join(process.cwd(), pathname === '/' ? 'web/index.html' : pathname);
      res.setHeader('Content-Type', { '.html': 'text/html', '.js': 'application/javascript', '.css': 'text/css', '.svg': 'image/svg+xml', '.woff': 'font/woff' }[path.extname(file)] || 'application/octet-stream');
      res.end(await fs.readFile(file));
    } catch { res.writeHead(404); res.end('missing'); }
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  base = `http://127.0.0.1:${server.address().port}`;
  await fs.writeFile(`${evidence}/server.json`, JSON.stringify({ pid: process.pid, port: server.address().port, llm: 0, mail: 0, db: null }));
});
test.afterAll(async () => {
  const port = server?.address()?.port;
  if (server?.listening) await new Promise(resolve => server.close(resolve));
  await fs.writeFile(`${evidence}/cleanup.json`, JSON.stringify({ port, listening: server?.listening }));
});
const deferred = () => { let resolve; const promise = new Promise(r => { resolve = r; }); return { promise, resolve }; };
const snap = async (page, name, width) => {
  await page.evaluate(() => document.fonts.ready);
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
  const action = page.locator('.next-situation-button');
  if (await action.count()) {
    const box = await action.boundingBox(); expect(box.x).toBeGreaterThanOrEqual(0); expect(box.x + box.width).toBeLessThanOrEqual(width + 1);
  }
  await page.screenshot({ path: `${evidence}/${name}-${width}.png`, fullPage: true, scale: 'css' });
};

for (const width of [1440, 390, 320]) test(`R3/R4/R6/R7/R9 current Next, time, focus and recovery ${width}`, async ({ page }) => {
  test.setTimeout(20000);
  await page.setViewportSize({ width, height: width === 1440 ? 1000 : 844 });
  await page.clock.install({ time: new Date('2026-11-17T12:00:00Z') });
  const errors = []; page.on('pageerror', error => errors.push(error.message));
  const run = await draftFixture(page), active = structuredClone(run.model);
  await page.goto(`${base}/?screen=interview`); await expect(page.locator('#interview-textarea')).toBeEnabled();
  Object.assign(run.model, { current_situation: null, between_situations: true, blocking_system_wait: false,
    status: { ...run.model.status, collection_status: 'paused' }, trace: { turns: [], events: [] } });
  await page.clock.runFor(1300);
  const next = page.locator('.next-situation-button'), timer = page.locator('#interview-timer-badge');
  await expect(next).toHaveText('Приступить к следующей ситуации');
  await expect(page.locator('.preparation-time-notice')).toHaveText('Время на ответы сейчас не расходуется. Общий срок завершения оценки продолжает идти');
  await expect(timer).toHaveText('Время выполнения · 120:00'); await snap(page, 'paused', width);
  let posts = 0, checks = 0, operationId, phase = 'running';
  const entered = deferred(), release = deferred();
  await page.route('**/users/assessment/m7/cycles/synthetic-cycle/next', async route => {
    posts++; operationId = route.request().postDataJSON().idempotency_key; entered.resolve(); await release.promise;
    try { await route.abort('failed'); } catch { /* The controlled deadline may have already aborted this request. */ }
  });
  await page.route('**/users/assessment/cycles/preparation/**', route => {
    checks++; expect(new URL(route.request().url()).pathname).toBe('/users/assessment/cycles/preparation/' + operationId);
    return route.fulfill({ json: { operation_id: operationId, status: phase,
      preparation: run.model.preparation_operation?.preparation,
      ...(phase === 'completed' ? { result: { decision: { status: 'SELECTED' } } } : {}) } });
  });
  await next.click(); await entered.promise;
  await page.evaluate(() => { window.qa03OldCard = document.querySelector('.interview-return-card'); });
  run.model.preparation_operation = { operation_id: operationId, status: 'queued', preparation: { ...preparationModel,
    operation_id: operationId, kind: 'next', status: 'queued', stage_label: 'Готовим следующую ситуацию',
    started_at: '2026-11-17T11:30:00Z', stage_started_at: '2026-11-17T11:33:00Z', read_at: '2026-11-17T12:00:00Z' } };
  await page.clock.runFor(1300); await expect(next).toHaveText('Проверить состояние'); await expect(next).toBeDisabled();
  expect(await page.evaluate(() => qa03OldCard.isConnected)).toBe(false);
  run.model.preparation_operation.status = 'running'; run.model.preparation_operation.preparation.status = 'running'; await page.clock.runFor(1300); await expect(next).toBeDisabled();
  await snap(page, 'running', width);
  if (width === 390) await page.clock.runFor(30001); // Real production POST deadline, virtual clock.
  release.resolve(); await expect(next).toBeEnabled(); await snap(page, 'recovered-button', width);
  await next.evaluate(button => { button.click(); button.click(); }); await expect(next).toBeEnabled();
  expect(posts).toBe(1); expect(checks).toBe(1);
  const root = page.locator('#interview-panel [data-preparation-status]');
  await root.locator('summary').click(); await root.getByRole('button', { name: 'Скопировать сведения' }).focus();
  await page.evaluate(() => { window.qa03Card = document.querySelector('.interview-return-card'); });
  const before = await page.evaluate(() => ({ y: scrollY, scroll: document.querySelector('#interview-scroll-area')?.scrollTop }));
  await page.clock.runFor(1300); await expect(next).toBeEnabled();
  await expect(root.locator('details')).toHaveAttribute('open', '');
  await expect(root.getByRole('button', { name: 'Скопировать сведения' })).toBeFocused();
  expect(await page.evaluate(() => qa03Card === document.querySelector('.interview-return-card'))).toBe(true);
  expect(await page.evaluate(() => ({ y: scrollY, scroll: document.querySelector('#interview-scroll-area')?.scrollTop }))).toEqual(before);
  // Successful response with unknown budget, then genuine GET failure, then recovery.
  run.model.status.remaining_seconds = null; await page.clock.runFor(1300); await expect(timer).toHaveText('Время недоступно');
  await expect(timer).not.toHaveClass(/is-low-time/); await snap(page, 'unknown', width);
  run.offline = true; await page.clock.runFor(1300);
  await expect(page.locator('.preparation-time-notice')).toContainText('Сведения о времени сейчас недоступны');
  await snap(page, 'read-error', width);
  run.offline = false; run.model.status.remaining_seconds = 7200; await page.clock.runFor(1300);
  await expect(timer).toHaveText('Время выполнения · 120:00'); await expect(next).toBeEnabled();
  // Readback of completed Next can only present the server-selected result.
  phase = 'completed'; Object.assign(run.model, active, { between_situations: false }); run.model.preparation_operation = undefined;
  await next.click(); await expect(page.locator('#interview-textarea')).toBeEnabled();
  expect(posts).toBe(1); expect(checks).toBe(2);
  expect(run.calls.filter(call => call.method === 'POST' && /\/start$|\/prepare$/.test(call.url))).toEqual([]);
  expect(run.unexpected).toEqual([]); expect(errors).toEqual([]);
  await fs.writeFile(`${evidence}/facts-${width}.json`, JSON.stringify({ posts, checks, sameCard: true, focusAndScrollPreserved: true, errors, unexpected: run.unexpected }, null, 2));
});

test('R1/R2 real polling continues across GETs slower than poll interval without overlapping requests', async ({ page }) => {
  test.setTimeout(20000); await page.clock.install({ time: new Date('2026-11-17T12:00:00Z') });
  const run = await draftFixture(page); await page.goto(`${base}/?screen=interview`);
  await expect(page.locator('#interview-textarea')).toBeEnabled();
  const held = [], release = [];
  await page.route('**/users/assessment/cycles/synthetic-cycle/runtime', async route => {
    const snapshot = structuredClone(run.model); const gate = deferred(); held.push(snapshot); release.push(gate.resolve); await gate.promise;
    await route.fulfill({ json: snapshot });
  });
  for (let n = 0; n < 3; n++) {
    run.model.status.remaining_seconds = 7100 - n;
    await page.clock.runFor(1300); await expect.poll(() => held.length).toBe(n + 1);
    await page.clock.runFor(2600); expect(held.length).toBe(n + 1);
    release[n](); await expect(page.locator('#interview-timer-badge')).toContainText(n === 0 ? '118:20' : n === 1 ? '118:19' : '118:18');
  }
  expect(run.unexpected).toEqual([]);
});
