import { expect, test } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';
import http from 'node:http';
import { draftFixture, preparationModel } from './fixtures/postw02-qa.mjs';

// Component geometry in a real browser. The owned HTTP/PG route is checked separately.
const css = ['tokens.css', 'base.css', 'components.css', 'screens/interview.css']
  .map((name) => fs.readFileSync(path.resolve('web/styles', name), 'utf8')).join('\n');
const evidence = path.resolve(process.env.REFUSAL_EVIDENCE || 'docs/evc/tasks/p4k-assessment-refusal-ui-01/evidence');

test('F09 Next card is readable at desktop, mobile and enlarged text', async ({ page }) => {
  fs.mkdirSync(evidence, { recursive: true });
  for (const [name, width, zoom] of [
    ['desktop-1440', 1440, 1], ['mobile-390', 390, 1],
    ['mobile-320', 320, 1], ['mobile-320-text-200', 320, 2],
  ]) {
    await page.setViewportSize({ width, height: 900 });
    await page.setContent(`<html lang="ru"><head><meta name="viewport" content="width=device-width,initial-scale=1"></head>
      <body><main class="interview-panel"><div class="interview-messages">
      <section class="interview-return-card"><h3>Ситуация 1 завершена</h3>
      <p>Ответы сохранены. Сейчас пауза: время на выполнение не расходуется.</p>
      <button type="button" class="primary-button">Проверить состояние</button>
      <p role="status">Подготовка продолжается. Очень длинное синтетическое пояснение: запрос
      к серверу завершился без ответа, операция продолжает выполняться и требует проверки состояния.</p>
      </section><textarea disabled aria-label="Ответ" placeholder="Ситуация завершена. Следующий ответ станет доступен после перехода."></textarea>
      </div></main></body></html>`);
    await page.addStyleTag({ content: css });
    if (zoom === 2) await page.evaluate(() => { document.documentElement.style.zoom = '2'; });
    const button = page.getByRole('button', { name: /Проверить состояние/ });
    await expect(button).toBeVisible();
    await button.focus();
    await expect(button).toBeFocused();
    await expect(page.getByRole('status')).toBeVisible();
    await expect(page.getByRole('textbox', { name: 'Ответ' })).toBeDisabled();
    const geometry = await page.evaluate(() => ({
      overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
      button: document.querySelector('.interview-return-card button').getBoundingClientRect().toJSON(),
      card: document.querySelector('.interview-return-card').getBoundingClientRect().toJSON(),
    }));
    expect(geometry.overflow, `${name} horizontal overflow`).toBeLessThanOrEqual(1);
    expect(geometry.button.width, `${name} button width`).toBeGreaterThan(180);
    expect(geometry.button.right, `${name} button within card`).toBeLessThanOrEqual(geometry.card.right + 1);
    await page.screenshot({ path: path.join(evidence, `f09-${name}.png`), fullPage: true });
  }
});


// Actual production bundle and ordinary Next/navigation; synthetic HTTP, no DB/LLM/mail.
let server, base;
test.beforeAll(async () => {
  fs.mkdirSync(evidence, { recursive: true });
  server = http.createServer((req, res) => {
    const pathname = new URL(req.url, 'http://localhost').pathname;
    const file = path.join(process.cwd(), pathname === '/' ? 'web/index.html' : pathname);
    try {
      res.setHeader('Content-Type', { '.html': 'text/html', '.js': 'application/javascript', '.css': 'text/css', '.svg': 'image/svg+xml' }[path.extname(file)] || 'application/octet-stream');
      res.end(fs.readFileSync(file));
    } catch { res.writeHead(404); res.end('missing'); }
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  base = `http://127.0.0.1:${server.address().port}`;
});
test.afterAll(async () => {
  if (server?.listening) await new Promise(resolve => server.close(resolve));
  fs.writeFileSync(path.join(evidence, 'cleanup.json'), JSON.stringify({ listening: server?.listening, db: null, llm: 0, mail: 0 }));
});
const refusal = 'Материалы ситуации не прошли обязательную проверку. Обратитесь к организатору оценки.';
const between = run => Object.assign(run.model, {
  current_situation: null, between_situations: true, blocking_system_wait: true,
  participant_progress: { planned_total: 8, last_completed_position_no: 3 },
});
const failedOperation = (id, message = refusal, retry = false) => ({ operation_id: id, status: 'failed', retry_allowed: retry,
  ...(message ? { error: { code: 'ASSESSMENT_AS_NOT_ADMITTED', message } } : {}),
  preparation: { ...preparationModel, operation_id: id, reference: 'P4K-' + id, kind: 'next', status: 'failed',
    explanation: 'Не удалось завершить подготовку. Проверяем материалы ситуации.', allowed_actions: retry ? ['retry'] : [],
    finished_at: '2026-11-19T12:00:00Z', read_at: '2026-11-19T12:00:00Z' } });

for (const width of [1440, 320]) test(`AC1/AC2 refusal survives polling, failed GET, reload and cabinet ${width}`, async ({ page }) => {
  test.setTimeout(30000);
  await page.setViewportSize({ width, height: 1000 });
  await page.clock.install({ time: new Date('2026-11-19T12:00:00Z') });
  const errors = []; page.on('pageerror', error => errors.push(error.message));
  const run = await draftFixture(page); between(run);
  const dashboard = { current_assessments: [{ cycle_id: 'synthetic-cycle', title: 'Синтетическая оценка',
    status: 'active', journey_state: 'active', status_label: 'Оценка начата', action: 'continue', button_label: 'Продолжить',
    current_position_no: 3, planned_total: 8 }] };
  const user = { id: 8, email: 'synthetic@example.test', full_name: 'Участник' };
  await page.route('**/users/8/session-bootstrap', route => route.fulfill({ json: { user, dashboard } }));
  await page.route('**/users/session/restore', route => route.fulfill({ json: { authenticated: true, user, dashboard } }));
  const savedTrace = structuredClone(run.model.trace);
  let posts = 0, checks = 0, operationId;
  await page.route('**/users/assessment/m7/cycles/synthetic-cycle/next', route => {
    posts++; operationId = route.request().postDataJSON().idempotency_key;
    run.model.preparation_operation = failedOperation(operationId);
    return route.fulfill({ json: run.model.preparation_operation });
  });
  await page.route('**/users/assessment/cycles/preparation/**', route => {
    checks++;
    expect(new URL(route.request().url()).pathname).toBe('/users/assessment/cycles/preparation/' + operationId);
    return route.fulfill({ json: run.model.preparation_operation });
  });
  await page.goto(`${base}/?screen=interview`);
  const card = page.locator('.interview-return-card'), next = page.locator('.next-situation-button');
  await next.click();
  const assertReason = async () => {
    await expect(card.locator('[data-preparation-explanation]')).toHaveText(refusal);
    await expect(card).not.toContainText('Не удалось завершить подготовку');
    await expect(card.locator('[data-next-preparation-feedback]')).toBeEmpty();
    await expect(next).toBeDisabled(); await expect(next).toHaveText('Подготовка недоступна');
    await expect(card).toHaveAttribute('data-preparation-operation', operationId);
    await expect(card).toContainText('Ситуация 3 завершена');
    await expect(page.locator('#interview-textarea')).toBeDisabled();
    expect((await card.innerText()).split(refusal).length - 1).toBe(1);
  };
  await assertReason();
  await page.clock.runFor(1400); await assertReason();
  run.offline = true; await page.clock.runFor(1400); await assertReason();
  await expect(card.locator('[data-preparation-notice]')).toContainText('Не удалось обновить состояние');
  run.offline = false; await page.clock.runFor(1400); await assertReason();
  await page.reload(); await assertReason();
  // A dashboard return is a read of the same Cycle, with no extra Next or Turn.
  await page.locator('#interview-profile-button').click();
  await expect(page.locator('#dashboard-panel')).toBeVisible();
  await page.getByRole('button', { name: 'Продолжить', exact: true }).click();
  await assertReason();
  expect(posts).toBe(1); expect(checks).toBe(0);
  expect(run.calls.filter(call => call.method === 'POST')).toEqual([]);
  expect(run.model.trace).toEqual(savedTrace);
  expect(run.unexpected).toEqual([]); expect(errors).toEqual([]);
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
  await page.screenshot({ path: path.join(evidence, `refusal-${width}.png`), fullPage: true });
  fs.writeFileSync(path.join(evidence, `facts-${width}.json`), JSON.stringify({ posts, checks, sameCycle: run.model.cycle_id,
    operationId, traceUnchanged: true, cabinetReturn: true, errors, unexpected: run.unexpected }, null, 2));
});

test('AC3/AC4 legacy fallback, text safety, new operation, running, retry and ready AS', async ({ page }) => {
  test.setTimeout(30000);
  await page.clock.install({ time: new Date('2026-11-19T12:00:00Z') });
  const run = await draftFixture(page), active = structuredClone(run.model); between(run);
  run.model.preparation_operation = failedOperation('old', null);
  await page.goto(`${base}/?screen=interview`);
  const card = page.locator('.interview-return-card'), next = page.locator('.next-situation-button');
  await expect(card).toContainText('Не удалось завершить подготовку');
  const markup = '<img src=x onerror="window.unsafeFailure=true">';
  run.model.preparation_operation = failedOperation('safe-text', markup);
  await page.clock.runFor(1400);
  await expect(card.locator('[data-preparation-explanation]')).toHaveText(markup);
  expect(await card.locator('img').count()).toBe(0);
  expect(await page.evaluate(() => window.unsafeFailure)).toBeUndefined();
  run.model.preparation_operation = { operation_id: 'running-new', status: 'running',
    preparation: { ...preparationModel, operation_id: 'running-new', reference: 'P4K-running-new', kind: 'next',
      read_at: '2026-11-19T12:00:00Z' } };
  await page.clock.runFor(1400);
  await expect(card).not.toContainText(markup); await expect(next).toHaveText('Проверить состояние');
  await expect(next).toBeEnabled();
  let checks = 0, posts = 0;
  await page.route('**/users/assessment/cycles/preparation/**', route => {
    checks++; expect(route.request().url()).toContain('/running-new');
    return route.fulfill({ json: run.model.preparation_operation });
  });
  await next.click(); await expect(next).toBeEnabled(); expect(checks).toBe(1);
  run.model.preparation_operation = failedOperation('retryable', 'Временная безопасная причина.', true);
  await page.clock.runFor(1400); await expect(next).toHaveText('Повторить подготовку'); await expect(next).toBeEnabled();
  await page.route('**/users/assessment/m7/cycles/synthetic-cycle/next', route => {
    posts++;
    const id = route.request().postDataJSON().idempotency_key;
    expect(id).not.toBe('retryable');
    Object.assign(run.model, active, { preparation_operation: undefined, between_situations: false });
    return route.fulfill({ json: { operation_id: id, status: 'completed', result: { decision: { status: 'SELECTED' } } } });
  });
  await next.click(); await expect(page.locator('#interview-textarea')).toBeEnabled();
  await expect(page.locator('#interview-messages')).not.toContainText('Временная безопасная причина.');
  expect(posts).toBe(1); expect(checks).toBe(1);
  expect(run.calls.filter(call => call.method === 'POST')).toEqual([]);
  expect(run.unexpected).toEqual([]);
});
