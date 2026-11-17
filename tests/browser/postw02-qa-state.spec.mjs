// Actual published bundle + controlled HTTP/clock. Zero real LLM/mail/DB.
import { test, expect } from '@playwright/test';
import http from 'node:http';
import fs from 'node:fs/promises';
import path from 'node:path';
import { draftSlot } from '../../web/js/answer-drafts.js';
import { draftFixture, dashboardFixture, preparationModel } from './fixtures/postw02-qa.mjs';

const evidence = process.env.POSTW_QA_EVIDENCE || '.test-stand/postw02-qa';
let server, base;
test.beforeAll(async () => {
  await fs.mkdir(evidence, { recursive: true });
  server = http.createServer(async (req, res) => {
    try {
      const pathname = new URL(req.url, 'http://localhost').pathname;
      const file = path.join(process.cwd(), pathname === '/' ? 'web/index.html' : pathname);
      res.setHeader('Content-Type', { '.html': 'text/html', '.js': 'application/javascript', '.css': 'text/css', '.svg': 'image/svg+xml', '.woff': 'font/woff' }[path.extname(file)] || 'application/octet-stream');
      res.end(await fs.readFile(file));
    } catch { res.statusCode = 404; res.end('missing'); }
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  base = `http://127.0.0.1:${server.address().port}`;
  await fs.writeFile(`${evidence}/server.json`, JSON.stringify({ pid: process.pid, port: server.address().port, llm: 0, mail: 0, db: null }));
});
test.afterAll(async () => {
  const port = server?.address()?.port;
  if (server?.listening) await new Promise(resolve => server.close(resolve));
  await fs.writeFile(`${evidence}/cleanup.json`, JSON.stringify({ port, listening: server?.listening, llm: 0, mail: 0, db: null }));
});
const deferred = () => { let resolve; const promise = new Promise(r => { resolve = r; }); return { promise, resolve }; };
const snapshot = async (page, name, width, facts) => {
  await page.evaluate(async () => document.fonts.ready);
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
  await page.screenshot({ path: `${evidence}/${name}-${width}.png`, fullPage: true, scale: 'css' });
  await fs.writeFile(`${evidence}/${name}-${width}.json`, JSON.stringify(facts, null, 2));
};

for (const width of [1440, 390]) {
  test(`QA A1/A4 delayed choice, reload, explicit resolution and first submit ${width}`, async ({ page }) => {
    test.setTimeout(20000);
    await page.setViewportSize({ width, height: width === 1440 ? 1000 : 844 });
    await page.clock.install({ time: new Date('2026-11-17T12:00:00Z') });
    const run = await draftFixture(page);
    await page.goto(`${base}/?screen=interview`);
    const field = page.locator('#interview-textarea'), submit = page.locator('#interview-submit-button');
    await expect(field).toBeEnabled(); await field.fill('Локальный черновик'); await page.clock.runFor(800);
    const saved = run.drafts[draftSlot(run.model)]; Object.assign(saved, { text: 'Другой сохранённый вариант', revision: 'other-device', version: saved.version + 1 });
    await field.fill('Локальный текст до выбора'); await page.clock.runFor(800);
    await expect(submit).toBeDisabled();
    const entered = deferred(), release = deferred(); let held = false;
    await page.route('**/draft', async route => {
      if (route.request().method() === 'GET' && !held) { held = true; entered.resolve(); await release.promise; }
      return route.fallback();
    });
    await page.getByRole('button', { name: 'Использовать другой сохранённый вариант', exact: true }).click();
    await entered.promise;
    await expect(field).toBeEnabled();
    for (const choice of await page.locator('#interview-draft-actions button').all()) await expect(choice).toBeDisabled();
    const text = 'Новый текст после выбора\nСинтетический материал участника';
    await field.fill(text); release.resolve();
    await expect(page.locator('#interview-draft-status')).toHaveText('Вы изменили текст. Выберите, какой вариант сохранить');
    await expect(field).toHaveValue(text); await expect(submit).toBeDisabled();
    const local = await page.evaluate(() => Object.keys(localStorage).filter(k => k.startsWith('agent4k.answerDraft:')).map(k => JSON.parse(localStorage.getItem(k))));
    expect(local.some(r => r.text === text && r.confirmed === false)).toBe(true);
    expect(run.calls.filter(c => c.url.endsWith('/turns') && c.method === 'POST')).toHaveLength(0);
    await snapshot(page, 'draft-new-text', width, { local, posts: 0, delayedRead: held });
    await page.reload(); await expect(field).toHaveValue(text); await expect(submit).toBeDisabled();
    await page.getByRole('button', { name: 'Оставить текст из этой вкладки', exact: true }).click();
    await expect(page.locator('#interview-draft-status')).toHaveText('Черновик сохранён'); await expect(submit).toBeEnabled();
    expect(run.calls.filter(c => c.url.endsWith('/turns') && c.method === 'POST')).toHaveLength(0);
    await submit.click(); await expect.poll(() => Boolean(run.receipt)).toBe(true);
    expect(run.receipt.content_text).toBe(text);
    expect(run.calls.filter(c => c.url.endsWith('/turns') && c.method === 'POST')).toHaveLength(1);
    expect(run.unexpected).toEqual([]);
    await fs.writeFile(`${evidence}/draft-submit-${width}.json`, JSON.stringify({ posts: 1, text: run.receipt.content_text, mode: 'controlled API, production bundle' }));
  });

  test(`QA B1/B2/B3/B4 dashboard refresh, keyboard, selection and scroll ${width}`, async ({ page, context }) => {
    test.setTimeout(20000);
    await context.grantPermissions(['clipboard-read', 'clipboard-write']);
    await page.setViewportSize({ width, height: width === 1440 ? 1000 : 844 });
    await page.clock.install({ time: new Date('2026-11-17T12:00:00Z') });
    const run = await dashboardFixture(page);
    run.card.preparation = { ...preparationModel, read_at: '2026-11-17T12:00:00Z', started_at: '2026-11-17T11:50:00Z',
      stage_started_at: '2026-11-17T11:53:00Z', last_progress_at: '2026-11-17T11:53:00Z' };
    await page.goto(base);
    const card = page.locator('article[data-cycle-id="cabinet-cycle"]'), details = card.locator('details');
    const summary = card.locator('summary'), copy = card.getByRole('button', { name: 'Скопировать сведения', exact: true });
    await summary.focus(); await page.keyboard.press('Enter'); await expect(details).toHaveAttribute('open', '');
    await page.keyboard.press('Tab'); await expect(copy).toBeFocused();
    await page.evaluate(() => { window.qaDetails = document.querySelector('article[data-cycle-id="cabinet-cycle"] details'); });
    const before = await page.evaluate(() => ({ y: scrollY, cardTop: document.querySelector('article[data-cycle-id="cabinet-cycle"]').getBoundingClientRect().top }));
    run.card.preparation = { ...run.card.preparation, stage_label: 'Сохраняем подготовленные материалы', read_at: '2026-11-17T12:00:30Z' };
    const reads = () => run.calls.filter(c => c.pathname.endsWith('/session-bootstrap')).length;
    const firstRead = reads(); await page.clock.fastForward(30001);
    await expect.poll(reads).toBeGreaterThan(firstRead);
    await expect(card.locator('[data-preparation-stage]')).toHaveText('Сохраняем подготовленные материалы');
    await expect(copy).toBeFocused(); await expect(details).toHaveAttribute('open', '');
    expect(await page.evaluate(() => qaDetails === document.querySelector('article[data-cycle-id="cabinet-cycle"] details'))).toBe(true);
    const after = await page.evaluate(() => ({ y: scrollY, cardTop: document.querySelector('article[data-cycle-id="cabinet-cycle"]').getBoundingClientRect().top }));
    expect(Math.abs(before.y - after.y)).toBeLessThanOrEqual(1); expect(Math.abs(before.cardTop - after.cardTop)).toBeLessThanOrEqual(1);
    await copy.click(); await expect(card.locator('[data-preparation-copied]')).toHaveText('Сведения скопированы');
    expect(await page.evaluate(() => navigator.clipboard.readText())).toContain('Сохраняем подготовленные материалы');
    // Selection in unchanged facts survives a real visibility-triggered refresh.
    await page.evaluate(() => {
      const node = document.querySelector('article[data-cycle-id="cabinet-cycle"] [data-preparation-reference]');
      const range = document.createRange(); range.selectNodeContents(node); const s = getSelection(); s.removeAllRanges(); s.addRange(range);
    });
    const selected = await page.evaluate(() => getSelection().toString());
    run.card.preparation.read_at = '2026-11-17T12:00:31Z';
    const visibleRead = reads(); await page.evaluate(() => document.dispatchEvent(new Event('visibilitychange')));
    await expect.poll(reads).toBeGreaterThan(visibleRead);
    await expect.poll(() => page.evaluate(() => getSelection().toString())).toBe(selected);
    await snapshot(page, 'dashboard-refreshed', width, { before, after, selected, reads: reads(), clipboard: 'current stage copied', sameDetailsNode: true });
    // Latest toggle during a delayed request wins in both directions.
    for (const open of [false, true]) {
      const entered = deferred(), release = deferred();
      await page.route('**/session-bootstrap*', async route => { entered.resolve(); await release.promise; return route.fallback(); });
      await page.evaluate(() => document.dispatchEvent(new Event('visibilitychange'))); await entered.promise;
      run.card.preparation = { ...run.card.preparation, stage_label: `Обновление сведений ${open ? 'после раскрытия' : 'после закрытия'}` };
      await summary.click(); release.resolve();
      await expect(card.locator('[data-preparation-stage]')).toHaveText(run.card.preparation.stage_label);
      await expect.poll(() => details.evaluate(n => n.open)).toBe(open);
      await page.unroute('**/session-bootstrap*');
    }
    // A read error retains details; existing manual retry updates the same nodes.
    run.journey.readFailure = true; await page.evaluate(() => document.dispatchEvent(new Event('visibilitychange')));
    await expect(page.locator('#dashboard-refresh-status')).toBeVisible(); await expect(details).toHaveAttribute('open', '');
    run.journey.readFailure = false; await page.locator('#dashboard-refresh-button').click();
    await expect(page.locator('#dashboard-refresh-status')).toBeHidden(); await expect(details).toHaveAttribute('open', '');
    // Reordering uses Cycle identity; operation replacement starts closed.
    const second = { ...run.card, cycle_id: 'another-cycle', title: 'Другая синтетическая оценка' };
    run.dashboard.current_assessments = [second, run.card]; await copy.focus();
    await page.evaluate(() => document.dispatchEvent(new Event('visibilitychange')));
    await expect(page.locator('#current-assessments article').first()).toHaveAttribute('data-cycle-id', 'another-cycle');
    await expect(copy).toBeFocused(); await expect(details).toHaveAttribute('open', '');
    await expect(page.locator('article[data-cycle-id="another-cycle"] details')).not.toHaveAttribute('open');
    run.card.preparation = { ...run.card.preparation, reference: 'P4K-NEW-OPERATION', operation_id: 'new-operation' };
    await page.evaluate(() => document.dispatchEvent(new Event('visibilitychange')));
    await expect(details).not.toHaveAttribute('open'); await expect(summary).toBeFocused();
    await summary.click(); await copy.focus(); run.card.preparation = null;
    await page.evaluate(() => document.dispatchEvent(new Event('visibilitychange')));
    await expect(details).toHaveCount(0); await expect(card.locator('[data-dashboard-action]')).toBeFocused();
    expect(run.unexpected).toEqual([]);
    await fs.writeFile(`${evidence}/dashboard-actions-${width}.json`, JSON.stringify({ periodic: true, visibility: true, manual: true, latestToggleBothWays: true, reordered: true, operationReset: true, removedFallback: true }));
  });
}
