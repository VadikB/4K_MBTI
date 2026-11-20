// Production bundle, controlled HTTP and clock; one worker, zero LLM/mail/DB.
import { test, expect } from '@playwright/test';
import http from 'node:http';
import fs from 'node:fs/promises';
import path from 'node:path';
import { draftFixture } from './fixtures/postw02-qa.mjs';

const evidence = process.env.QA04_EVIDENCE || 'docs/evc/tasks/p4k-postw02-qa-04/evidence/browser';
const reference = process.env.POSTW02_REFERENCE;
let server, base;
test.beforeAll(async () => {
  await fs.mkdir(evidence, { recursive: true });
  server = http.createServer(async (req, res) => {
    try {
      const pathname = new URL(req.url, 'http://localhost').pathname;
      const file = pathname.startsWith('/reference/') && reference
        ? path.join(reference, 'dist', pathname.slice('/reference/'.length))
        : path.join(process.cwd(), pathname === '/' ? 'web/index.html' : pathname);
      res.setHeader('Content-Type', { '.html': 'text/html', '.js': 'application/javascript', '.mjs': 'application/javascript',
        '.css': 'text/css', '.svg': 'image/svg+xml', '.woff': 'font/woff' }[path.extname(file)] || 'application/octet-stream');
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
const deferred = () => { let resolve; const promise = new Promise(r => { resolve = r; }); return { resolve, promise }; };
const bottom = page => page.locator('#interview-scroll-area').evaluate(n => n.scrollHeight - n.scrollTop - n.clientHeight);
const capture = async (page, name, width) => {
  await page.evaluate(() => document.fonts.ready);
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
  await page.screenshot({ path: `${evidence}/${name}-${width}.png`, fullPage: true, scale: 'css' });
};
const block = run => {
  run.model.current_situation.status = 'scenario_ended'; run.model.blocking_system_wait = true;
  run.model.finish_availability = { allowed: false, reason: 'ANALYSIS_PENDING' };
  run.model.pipeline = { status: 'running' };
};
const boot = async (page, width) => {
  await page.setViewportSize({ width, height: width === 1440 ? 1000 : 844 });
  await page.clock.install({ time: new Date('2026-11-18T09:00:00Z') });
  const errors = []; page.on('pageerror', error => errors.push(error.message));
  const run = await draftFixture(page);
  for (let i = 3; i <= 34; i++) run.model.trace.turns.push({ turn_id: `history-${i}`, sequence_no: i,
    speaker_type: i % 2 ? 'assessee' : 'character', content_text: `Сообщение ${i}. ` + 'Обсуждаем условия и порядок действий. '.repeat(4) });
  await page.goto(`${base}/?screen=interview`);
  await expect(page.locator('#interview-textarea')).toBeEnabled();
  await page.clock.runFor(300);
  return { run, errors };
};

for (const width of [1440, 390, 320]) {
  test(`C1-C8 own send, history, waiting, errors and allowed finish ${width}`, async ({ page }) => {
    const { run, errors } = await boot(page, width);
    const input = page.locator('#interview-textarea'), submit = page.locator('#interview-submit-button');
    const notice = page.locator('#interview-error'), area = page.locator('#interview-scroll-area');
    await input.fill('Мой новый ответ\nи обоснование'); await page.clock.runFor(900);
    await expect(page.locator('#interview-draft-status')).toHaveText('Черновик сохранён');
    // Set a settled reading position; CSS smooth scrolling must not race the poll.
    await area.evaluate(n => n.scrollTo({ top: 350, behavior: 'instant' }));
    const oldTop = await area.evaluate(n => n.scrollTop);
    expect(oldTop).toBe(350);
    run.model.trace.turns.push({ turn_id: 'background-update', sequence_no: 35, speaker_type: 'character', content_text: 'Фоновое дополнение условий.' });
    await page.clock.runFor(1500);
    expect(await area.evaluate(n => n.scrollTop)).toBe(oldTop);
    await expect(input).toHaveValue('Мой новый ответ\nи обоснование');
    await expect(page.locator('#interview-messages-scroll')).toBeVisible();
    await page.locator('#interview-messages-scroll').click(); await page.clock.runFor(800);
    await expect.poll(() => bottom(page)).toBeLessThanOrEqual(1);
    await area.evaluate(n => n.scrollTo({ top: 350, behavior: 'instant' }));
    const entered = deferred(), release = deferred(), readbackEntered = deferred(), releaseReadback = deferred();
    let posts = 0, holdReadback = false;
    await page.route('**/runtime', async route => {
      if (!holdReadback) return route.fallback();
      holdReadback = false; readbackEntered.resolve(); await releaseReadback.promise;
      return route.fulfill({ json: run.model });
    });
    await page.route('**/users/assessment/m5/situations/synthetic-as/turns', async route => {
      posts++; entered.resolve(); await release.promise;
      const body = route.request().postDataJSON();
      run.receipt = { turn_id: body.turn_id, request_id: body.request_id, content_text: body.content, speaker_type: 'assessee', sequence_no: 40 };
      run.model.trace.turns.push(run.receipt); block(run); holdReadback = true;
      await route.fulfill({ json: { turn: run.receipt } });
    });
    await submit.click(); await entered.promise; await page.clock.runFor(300);
    await expect.poll(() => bottom(page)).toBeLessThanOrEqual(1);
    await expect(page.locator('[data-pending-turn-id]')).toContainText('Мой новый ответ');
    await capture(page, 'pending', width);
    release.resolve(); await readbackEntered.promise;
    await expect(notice).toContainText('Ответ сохранён. Состояние обработки уточняется.');
    await expect(input).not.toHaveAttribute('placeholder', /Введите|Поясните|Напишите/);
    await expect(notice).not.toContainText(/Ожидайте завершения|сейчас не расходуется/);
    await capture(page, 'accepted-stale', width); releaseReadback.resolve();
    await expect(notice).toContainText('Ответ сохранён. Ожидайте завершения обработки.');
    await expect(notice).toContainText('Время на ответы сейчас не расходуется');
    await expect(submit).toHaveText('Отправить'); await expect(submit).toBeDisabled();
    await expect(page.locator('#interview-draft-status')).not.toContainText(/Ответ принят|Ответ сохранён/);
    await expect(page.locator('.interview-message-delivery:visible')).toHaveCount(0);
    const zones = await page.evaluate(() => {
      const history = document.querySelector('.interview-messages-shell'), status = document.querySelector('#interview-error'), form = document.querySelector('#interview-form');
      const css = getComputedStyle(status);
      return { historyBeforeStatus: Boolean(history.compareDocumentPosition(status) & Node.DOCUMENT_POSITION_FOLLOWING),
        statusBeforeForm: Boolean(status.compareDocumentPosition(form) & Node.DOCUMENT_POSITION_FOLLOWING),
        background: css.backgroundColor, borderLeft: css.borderLeftWidth, radius: css.borderRadius, font: css.fontFamily };
    });
    expect(zones.historyBeforeStatus && zones.statusBeforeForm).toBe(true);
    await capture(page, 'waiting', width);
    // A false/missing interval never inherits the prototype's stopped-time claim.
    run.model.blocking_system_wait = false; await page.clock.runFor(1500);
    await expect(notice).not.toContainText('сейчас не расходуется');
    run.model.blocking_system_wait = true; await page.clock.runFor(45001);
    await expect(notice).toContainText('Ответ сохранён. Обработка занимает больше времени.');
    await capture(page, 'delayed', width);
    run.offline = true; await notice.getByRole('button', { name: 'Проверить состояние' }).click();
    await expect(notice).toContainText('Ответ сохранён. Не удалось обновить состояние.');
    await expect(notice).not.toContainText(/продолжается|Ожидайте завершения|сейчас не расходуется/);
    await capture(page, 'read-error', width);
    run.offline = false; run.model.pipeline.status = 'failed';
    await notice.getByRole('button', { name: 'Проверить состояние' }).click();
    await expect(notice).toContainText('Ответ сохранён. Не удалось завершить обработку.');
    expect(await notice.evaluate(n => getComputedStyle(n).fontFamily.startsWith('Onest'))).toBe(true);
    await expect(notice).toHaveCSS('border-radius', '0px');
    await expect(page.locator('#interview-finish-button')).toBeHidden();
    await capture(page, 'failed', width);
    run.model.pipeline.status = 'running'; run.model.blocking_system_wait = false;
    run.model.clarification = { id: '00000000-0000-4000-8000-000000000099', status: 'ASK',
      question_turn_id: 'new-question', question: { text: 'Почему вы выбрали этот порядок действий?' } };
    await notice.getByRole('button', { name: 'Проверить состояние' }).click();
    await expect(input).toBeEnabled(); await expect(submit).toHaveText('Отправить'); await expect(notice).toBeHidden();
    await page.clock.runFor(1300); await expect(submit).toHaveText('Отправить');
    await capture(page, 'new-ask', width);
    run.model.clarification.response_outcome = 'answered'; run.model.clarification.answer_turn_id = run.receipt.turn_id;
    run.model.finish_availability = { allowed: true }; await page.clock.runFor(1500);
    await expect(input).toBeDisabled(); await expect(input).toHaveAttribute('placeholder', 'Ответы приняты. Можно завершить ситуацию.');
    await expect(page.locator('#interview-finish-button')).toBeVisible(); await expect(page.locator('#interview-finish-button')).toBeEnabled();
    await expect(notice).toBeHidden(); await capture(page, 'finish-allowed', width);
    expect(posts).toBe(1); expect(run.unexpected).toEqual([]); expect(errors).toEqual([]);
    await fs.writeFile(`${evidence}/facts-${width}.json`, JSON.stringify({ zones, posts, oldTop, ownPendingVisible: true,
      draftRetainedOnPoll: true, waitingDelayedReadErrorFailed: true, askAndFinish: true, pageErrors: errors }, null, 2));
  });

  test(`C6 unknown receipt checks original ID without retrying POST ${width}`, async ({ page }) => {
    const { run, errors } = await boot(page, width);
    let body, posts = 0, reads = 0, accepted = false;
    await page.route('**/users/assessment/m5/situations/synthetic-as/turns', route => {
      posts++; body = route.request().postDataJSON(); return route.abort('failed');
    });
    await page.route('**/answer-status?**', route => {
      reads++; const q = new URL(route.request().url()).searchParams;
      expect(q.get('request_id')).toBe(body.request_id); expect(q.get('turn_id')).toBe(body.turn_id);
      if (!accepted) return route.abort('failed');
      return route.fulfill({ json: { status: 'accepted', cycle_id: run.model.cycle_id, assessment_situation_id: 'synthetic-as',
        request_id: body.request_id, turn_id: body.turn_id, clarification_id: null,
        processing_status: 'applied', turn: run.receipt } });
    });
    await page.locator('#interview-textarea').fill('Ответ с неизвестным исходом');
    await page.locator('#interview-submit-button').click();
    const notice = page.locator('#interview-error'); await expect(notice).toContainText('Отправка не подтверждена.');
    await expect(page.locator('.interview-timer-caption')).toHaveText('Последний известный остаток');
    await expect(notice).not.toContainText('Ответ сохранён'); await capture(page, 'unknown-receipt', width);
    await notice.getByRole('button', { name: 'Проверить отправку' }).click();
    await expect(notice.getByRole('button')).toBeEnabled(); expect(reads).toBeGreaterThan(0); expect(posts).toBe(1);
    await expect(page.locator('#interview-textarea')).toHaveValue('Ответ с неизвестным исходом');
    // Later exact receipt/trace reconciles the lost ACK without carrying its
    // accepted revision into the next dialogue draft slot.
    accepted = true;
    run.receipt = { turn_id: body.turn_id, request_id: body.request_id, speaker_type: 'assessee', sequence_no: 40, content_text: body.content };
    run.model.trace.turns.push(run.receipt);
    await notice.getByRole('button', { name: 'Проверить отправку' }).click();
    await expect(page.locator('#interview-textarea')).toHaveValue(''); expect(posts).toBe(1);
    expect(errors).toEqual([]); expect(run.unexpected).toEqual([]);
  });
}

test('C8 reference v10 zones use the same notice palette, radius and composer action', async ({ page }) => {
  test.skip(!reference, 'Local v10 archive must be supplied for comparison');
  const facts = {};
  for (const width of [1440, 390, 320]) {
    await page.setViewportSize({ width, height: width === 1440 ? 1000 : 844 });
    await page.goto(`${base}/reference/screen.html?scene=assessment-waiting`);
    await expect(page.locator('.processing-notice')).toBeVisible();
    await expect(page.locator('#answer-form button')).toHaveText('Отправить');
    facts[width] = await page.locator('.processing-notice').evaluate(n => {
      const css = getComputedStyle(n); return { background: css.backgroundColor, borderLeft: css.borderLeftWidth, radius: css.borderRadius, font: css.fontFamily };
    });
    const product = JSON.parse(await fs.readFile(`${evidence}/facts-${width}.json`, 'utf8')).zones;
    for (const property of ['background', 'borderLeft', 'radius']) expect(product[property]).toBe(facts[width][property]);
    expect(product.font.startsWith('Onest')).toBe(true);
    await capture(page, 'reference-waiting', width);
  }
  await fs.writeFile(`${evidence}/reference-zones.json`, JSON.stringify(facts, null, 2));
});

test('ASUX 02.1 shows the public format before the first Turn and then uses the actual ASK', async ({ page }) => {
  await page.clock.install({ time: new Date('2026-11-18T09:00:00Z') });
  const { model } = await draftFixture(page);
  const current = model.current_situation;
  const input = page.locator('#interview-textarea');
  const format = page.locator('.interview-response-format');
  const yourTurn = page.locator('.interview-your-turn');
  model.trace.turns = [];
  current.response_format = 'written';
  current.participant_payload = {
    ...current.participant_payload, case_id: 'CASE.SPEC.02',
    assessee_position: 'Специалист', assessee_task: 'Сопоставьте материалы и напишите свою рекомендацию.',
  };
  await page.goto(`${base}/?screen=interview`);
  await expect(format).toHaveText('Письменное задание');
  await expect(input).toHaveAttribute('placeholder', 'Напишите свой ответ…');
  await expect(yourTurn).toBeVisible();
  await expect(page.locator('.product-situation-role')).toContainText('Специалист');
  await expect(page.locator('.product-situation-message')).toContainText(current.participant_payload.assessee_task);
  current.response_format = 'dialogue';
  await page.clock.runFor(1600);
  await expect(format).toHaveText('Диалог');
  await expect(input).toHaveAttribute('placeholder', /собеседнику/);
  current.response_format = null;
  await page.clock.runFor(1600);
  await expect(format).toHaveText('Оценочная ситуация');
  await expect(input).toHaveAttribute('placeholder', 'Напишите свой ответ…');
  current.status = 'scenario_ended';
  model.clarification = { id: 'ask-1', status: 'ASK', question_turn_id: 'q-1', question: { text: 'Почему?' } };
  await page.clock.runFor(1600);
  await expect(format).toHaveText('Уточнение');
  await expect(input).toHaveAttribute('placeholder', 'Ответьте на уточнение…');
  await expect(yourTurn).toBeVisible();
  model.clarification.response_outcome = 'answered';
  await page.clock.runFor(1600);
  await expect(yourTurn).toBeHidden();
});

for (const width of [1440, 390, 320]) {
  test(`ASUX 02.2 eight lines, keyboard and history at ${width}`, async ({ page }) => {
    const { run } = await boot(page, width);
    const input = page.locator('#interview-textarea');
    const submit = page.locator('#interview-submit-button');
    const materials = page.locator('.product-situation-materials');
    const history = page.locator('#interview-scroll-area');
    await materials.locator('summary').click();
    await expect(materials).toHaveJSProperty('open', true);
    await input.fill('Одна строка.');
    const initialHeight = (await input.boundingBox()).height;
    const text = Array.from({ length: 8 }, (_, i) => `Строка ${i + 1}.`).join('\n');
    await input.fill(text);
    const geometry = await input.evaluate(element => {
      const style = getComputedStyle(element);
      const number = name => Number.parseFloat(style[name]);
      return { height: element.clientHeight, scroll: element.scrollHeight,
        lines: (element.clientHeight - number('paddingTop') - number('paddingBottom')) / number('lineHeight') };
    });
    expect(geometry.lines).toBe(4);
    expect(geometry.height).toBeGreaterThan(initialHeight);
    expect(geometry.scroll).toBeGreaterThan(geometry.height);
    if (width <= 390) {
      // Chromium headless has no system IME. Exercise the same visualViewport
      // resize event with the keyboard-sized visible area and the field focused.
      await page.evaluate(() => {
        Object.defineProperty(visualViewport, 'height', { configurable: true, value: 450 });
        visualViewport.dispatchEvent(new Event('resize'));
      });
    }
    const action = await submit.boundingBox();
    expect(action.y + action.height).toBeLessThanOrEqual(width <= 390 ? 450 : 1000);
    await page.keyboard.press('Tab');
    await expect(submit).toBeFocused();
    await expect(input).toHaveValue(text);
    // Let the preceding draft PUT finish before the fixture advances its
    // server-owned dialogue slot to the newly published character Turn.
    await page.clock.runFor(1200);
    await expect(page.locator('#interview-draft-status')).toHaveText('Черновик сохранён');
    await history.evaluate(node => node.scrollTo({ top: 280, behavior: 'instant' }));
    await page.clock.runFor(300);
    const readingPosition = await history.evaluate(node => node.scrollTop);
    expect(readingPosition).toBeGreaterThan(0);
    run.model.trace.turns.push({ turn_id: 'new-background', sequence_no: 60,
      speaker_type: 'character', speaker_name: 'Марина', content_text: 'Поступила новая вводная.' });
    await page.clock.runFor(1600);
    await expect(materials).toHaveJSProperty('open', true);
    await expect(input).toHaveValue(text);
    await expect(submit).toBeFocused();
    await expect(page.locator('.interview-messages')).toContainText('Поступила новая вводная.');
    await page.clock.runFor(300);
    expect(await history.evaluate(node => node.scrollTop)).toBe(readingPosition);
  });
}

test('ASUX 03.1 proven rejection, retry and cancel finish with a draft', async ({ page }) => {
  const { run } = await boot(page, 390);
  const input = page.locator('#interview-textarea'), notice = page.locator('#interview-error');
  const answer = 'Повторите этот синтетический ответ.';
  const attempts = [];
  await page.route('**/users/assessment/m5/situations/synthetic-as/turns', async route => {
    const data = route.request().postDataJSON();
    attempts.push(data);
    if (attempts.length === 1) return route.fulfill({ status: 409, json: { detail: 'M5_STATE_REVISION_CONFLICT' } });
    run.receipt = { turn_id: data.turn_id, request_id: data.request_id, content_text: data.content,
      speaker_type: 'assessee', sequence_no: 50 };
    run.model.trace.turns.push(run.receipt);
    await route.fulfill({ json: { turn: run.receipt } });
  });
  // The standard fixture accepts dialogs, so replace its listener for this check.
  page.removeAllListeners('dialog');
  page.once('dialog', async dialog => {
    expect(dialog.message()).toContain('остался черновик');
    await dialog.dismiss();
  });
  await input.fill(answer);
  await page.locator('#interview-finish-button').click();
  await expect(input).toBeFocused();
  await expect(input).toHaveValue(answer);
  expect(run.calls.some(call => call.url.endsWith('/transitions'))).toBe(false);
  await page.locator('#interview-submit-button').click();
  await expect(notice).toContainText('Ошибка отправки. Текст сохранён в поле.');
  await expect(input).toHaveValue(answer);
  await expect(page.locator('.interview-message-delivery:visible')).toHaveCount(0);
  const retry = notice.getByRole('button', { name: 'Повторить отправку' });
  await retry.click();
  await expect(notice).toHaveText('Ответ сохранён.');
  expect(attempts.map(attempt => attempt.content)).toEqual([answer, answer]);
  expect(run.model.trace.turns.filter(turn => turn.content_text === answer)).toHaveLength(1);
  run.model.current_situation.status = 'closed';
  await page.clock.runFor(1600);
  await expect(input).toBeDisabled();
  await expect(page.locator('#interview-finish-button')).toBeHidden();
  await expect(page.getByRole('button', { name: 'Мои оценки' })).toBeEnabled();
});

test('ASUX 03.3 known Turn uses only addressed status reads after a lost read or failed processing', async ({ page }) => {
  const { run } = await boot(page, 390);
  const input = page.locator('#interview-textarea'), notice = page.locator('#interview-error');
  const reads = [];
  let original;
  const answer = 'Сохранённый ответ с неуспешной обработкой.';
  await page.route('**/answer-status?**', route => {
    const params = new URL(route.request().url()).searchParams;
    reads.push(Object.fromEntries(params));
    return route.fulfill({ json: { status: 'accepted', cycle_id: run.model.cycle_id, assessment_situation_id: 'synthetic-as',
      request_id: original.request_id, turn_id: original.turn_id, clarification_id: null,
      processing_status: run.model.answer_processing?.status || 'pending', turn: run.receipt } });
  });
  await page.route('**/users/assessment/m5/situations/synthetic-as/turns', async route => {
    original = route.request().postDataJSON();
    run.receipt = { turn_id: original.turn_id, request_id: original.request_id, content_text: original.content,
      speaker_type: 'assessee', sequence_no: 50 };
    run.model.trace.turns.push(run.receipt);
    run.model.blocking_system_wait = true;
    run.offline = true;
    await route.fulfill({ json: { turn: run.receipt } });
  });
  await input.fill(answer);
  await page.locator('#interview-submit-button').click();
  await expect(notice).toContainText('Ответ сохранён. Не удалось обновить состояние.');
  run.offline = false;
  run.model.blocking_system_wait = false;
  run.model.answer_processing = { turn_id: original.turn_id, request_id: original.request_id, status: 'failed' };
  await notice.getByRole('button', { name: 'Проверить состояние' }).click();
  await expect(notice).toContainText('Ответ сохранён. Сбой обработки.');
  await notice.getByRole('button', { name: 'Проверить состояние' }).click();
  await expect(notice).toContainText('Ответ сохранён. Сбой обработки.');
  expect(reads.length).toBeGreaterThanOrEqual(2);
  expect(reads.every(read => read.turn_id === original.turn_id && read.request_id === original.request_id)).toBe(true);
  expect(run.model.trace.turns.filter(turn => turn.content_text === answer)).toHaveLength(1);
  await expect(notice.getByRole('button', { name: /повторить/i })).toHaveCount(0);
});
