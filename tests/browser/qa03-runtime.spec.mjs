// Production bundle in Chromium with controlled HTTP/clock. One worker, no retries/LLM/mail/DB.
import { test, expect } from '@playwright/test';
import fs from 'node:fs/promises';
import http from 'node:http';
import path from 'node:path';
import { draftFixture } from './fixtures/postw02-qa.mjs';

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
  if (await action.isVisible()) {
    const box = await action.boundingBox(); expect(box).not.toBeNull(); expect(box.x).toBeGreaterThanOrEqual(0); expect(box.x + box.width).toBeLessThanOrEqual(width + 1);
  }
  await page.screenshot({ path: `${evidence}/${name}-${width}.png`, fullPage: true, scale: 'css' });
};

for (const width of [1440, 390, 320]) test(`ASUX-04 Next, receipt, budget and explicit presentation ${width}`, async ({ page }) => {
  test.setTimeout(30000);
  await page.setViewportSize({ width, height: 900 });
  await page.clock.install({ time: new Date('2026-11-17T12:00:00Z') });
  const errors = []; page.on('pageerror', error => errors.push(error.message));
  const run = await draftFixture(page), active = structuredClone(run.model);
  const deadline = '2026-11-20T12:00:00Z';
  const target = { assessment_situation_id: 'admitted-next', expected_plan_revision_id: 'saved-plan' };
  const user = { id: 8, email: 'synthetic@example.test', full_name: 'Участник' };
  const dashboard = { current_assessments: [{ cycle_id: run.model.cycle_id, title: 'Синтетическая оценка',
    status: 'paused', journey_state: 'between_situations', status_label: 'Между ситуациями',
    action: 'continue', button_label: 'Продолжить', planned_total: 8 }] };
  const requests = { prepare: 0, reads: 0, present: 0, effectivePresentations: 0 };
  const entered = deferred(), release = deferred();
  const install = async (tab) => {
    await tab.route('**/users/8/session-bootstrap', route => route.fulfill({ json: { user, dashboard } }));
    await tab.route('**/users/session/restore', route => route.fulfill({ json: { authenticated: true, user, dashboard } }));
    await tab.route('**/users/assessment/m7/cycles/synthetic-cycle/next', async route => {
      requests.prepare++;
      const { idempotency_key: id, after_assessment_situation_id: after } = route.request().postDataJSON();
      expect(id).toBe('next:synthetic-as'); expect(after).toBe('synthetic-as');
      run.model.preparation_operation = { operation_id: id, status: 'running' };
      entered.resolve();
      await release.promise;
      await route.abort('failed');
    });
    await tab.route('**/users/assessment/cycles/preparation/**', route => {
      requests.reads++;
      expect(route.request().url()).toContain('/preparation/next%3Asynthetic-as');
      return route.fulfill({ json: run.model.preparation_operation });
    });
    await tab.route('**/users/assessment/m7/cycles/synthetic-cycle/present-next', route => {
      requests.present++;
      expect(route.request().postDataJSON()).toEqual(target);
      if (run.model.between_situations) {
        requests.effectivePresentations++;
        Object.assign(run.model, active, { between_situations: false, next_presentation: null,
          current_situation: { ...active.current_situation, assessment_situation_id: target.assessment_situation_id },
          status: { collection_status: 'active', remaining_seconds: 2719, calendar_deadline: deadline } });
      }
      return route.fulfill({ json: { presentation: target } });
    });
  };
  await install(page);
  await page.route('**/users/assessment/m7/cycles/synthetic-cycle/finish-situation', route => {
    Object.assign(run.model, { current_situation: null, between_situations: true, blocking_system_wait: false,
      participant_progress: { planned_total: 8, last_completed_position_no: 1 },
      route: { ...run.model.route, positions: [{ position_no: 1, state: 'completed', current_assessment_situation_id: 'synthetic-as' }] },
      status: { collection_status: 'paused', remaining_seconds: 2720, calendar_deadline: deadline }, trace: null });
    return route.fulfill({ json: { status: 'between_situations', assessment_situation_id: 'synthetic-as' } });
  });
  run.model.current_situation.status = 'scenario_ended';
  run.model.finish_availability = { allowed: true };
  await page.goto(`${base}/?screen=interview`);
  await page.locator('#interview-finish-button').click();
  await entered.promise;
  const next = page.locator('.next-situation-button'), timer = page.locator('#interview-timer-badge');
  await expect(next).toHaveText('Проверить состояние');
  await expect(page.getByText('Ситуация 1 завершена', { exact: true })).toBeVisible();
  release.resolve();
  await expect.poll(() => requests.reads).toBe(1);
  await expect(next).toBeEnabled();
  await expect(timer).toHaveText('45:20');
  await snap(page, 'running', width);
  await next.focus();
  await page.clock.runFor(1300);
  await expect(next).toBeFocused();
  run.offline = true;
  await next.click();
  await expect(page.locator('[data-next-preparation-feedback]')).toContainText('Не удалось');
  await expect(timer).toHaveText('Время недоступно');
  run.offline = false;
  run.model.next_presentation = target;
  run.model.preparation_operation.status = 'completed';
  await next.click();
  await expect(next).toHaveText('Приступить к следующей ситуации');
  await expect(timer).toHaveText('45:20');
  await expect(page.locator('#interview-textarea')).toBeDisabled();
  await page.reload();
  await expect(next).toHaveText('Приступить к следующей ситуации');
  await page.locator('#interview-profile-button').click();
  await page.getByRole('button', { name: 'Продолжить', exact: true }).click();
  await expect(next).toHaveText('Приступить к следующей ситуации');
  await expect(next).toBeVisible();
  await snap(page, 'ready', width);
  const other = await page.context().newPage();
  await draftFixture(other, run); await install(other);
  await other.goto(`${base}/?screen=interview`);
  const otherNext = other.locator('.next-situation-button');
  await expect(otherNext).toHaveText('Приступить к следующей ситуации');
  expect(requests).toEqual({ prepare: 1, reads: 3, present: 0, effectivePresentations: 0 });
  await Promise.all([next.click(), otherNext.click()]);
  await expect(page.locator('#interview-textarea')).toBeEnabled();
  await expect(other.locator('#interview-textarea')).toBeEnabled();
  expect(requests).toEqual({ prepare: 1, reads: 3, present: 2, effectivePresentations: 1 });
  expect(run.model.status.calendar_deadline).toBe(deadline);
  expect(errors).toEqual([]);
  expect(run.unexpected).toEqual([]);
  await other.close();
  await fs.writeFile(`${evidence}/readback-${width}.json`, JSON.stringify({ ...requests, deadline,
    savedTimer: '45:20', cabinetReturn: true, reload: true, browserErrors: errors }, null, 2));
});
