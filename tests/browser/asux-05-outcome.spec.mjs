import { test, expect } from '@playwright/test';
import fs from 'node:fs/promises';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import { shortProgramReport } from './fixtures/m8-report.mjs';
import { startAdminProgramPreview } from '../../scripts/adm-program-ui-preview.mjs';

let preview;
test.beforeAll(async () => {
  preview = await startAdminProgramPreview({ port: 18985, adapter: async ({ url, response }) => {
    if (url.pathname !== '/') return false;
    response.setHeader('Content-Type', 'text/html; charset=utf-8');
    response.end(await fs.readFile('web/index.html'));
    return true;
  } });
});
test.afterAll(async () => { await preview?.close(); });

const A = 'cycle-a';
const B = 'cycle-b';
const evidenceDir = process.env.ASUX_05_EVIDENCE;
const referenceFile = process.env.ASUX_05_REFERENCE;
const user = { id: 18, email: 'participant@example.test', full_name: 'Участник' };
const waiting = { collection_status: 'collection_closed', results_status: 'processing',
  report_status: 'not_created', processing: { status: 'processing' },
  route_progress: { completed: null, total: 8 } };
const ready = { ...waiting, collection_status: 'calculated', results_status: 'ready',
  report_status: 'ready', processing: { status: 'completed' } };
const reportPath = (id) => '/users/assessment/m8/reports/' + id;
const statusPath = (cycleId) => '/users/assessment/m8/cycles/' + cycleId + '/status';
const outcomeTitle = (page) => page.locator('#processing-outcome-title');
const cardAction = (page, cycleId) => page.locator('#dashboard-panel button[data-cycle-id="' + cycleId + '"]');

async function fixture(page) {
  const dashboard = { completed_assessments: [A, B].map((cycleId, index) => ({
    cycle_id: cycleId, title: 'Оценка ' + (index === 0 ? 'А' : 'Б'), status: 'collection_closed',
    closed_at: '2026-11-19T12:00:00Z', planned_total: 3, action: 'open_processing', button_label: 'Проверить результат',
  })) };
  const run = {
    calls: [], unexpected: [], navigations: [],
    journey: { next_action: 'show_dashboard', report_status: 'ready',
      assessment: { runtime_kind: 'cycle', cycle_id: A, status: 'report_ready' } },
    status: { [A]: { ...ready, report_id: 'report-a' }, [B]: { ...waiting } },
    reports: {},
    handlers: {},
  };
  await page.route('**/users/**', (route) => {
    const request = route.request();
    const url = new URL(request.url()).pathname;
    const method = request.method();
    run.calls.push(method + ' ' + url);
    if (url === '/users/version') return route.fulfill({ json: { version: 'synthetic' } });
    if (['/users/session/restore', '/users/18/session-bootstrap'].includes(url)) {
      return route.fulfill({ json: { authenticated: true, user, dashboard } });
    }
    if (url === '/users/18/journey-state') return route.fulfill({ json: run.journey });
    if (url === '/users/18/acquaintance/issues') return route.fulfill({ json: { items: [] } });
    const statusCycle = [A, B].find((id) => url === statusPath(id));
    if (statusCycle && method === 'GET') {
      const snapshot = run.status[statusCycle];
      if (typeof snapshot === 'function') return snapshot(route);
      return route.fulfill({ json: { cycle_id: statusCycle, ...snapshot } });
    }
    if (url === '/users/assessment/m8/history') return route.fulfill({ json: { cycles: [] } });
    if (run.handlers[url]) return run.handlers[url](route);
    if (run.reports[url] && method === 'GET') return route.fulfill({ json: run.reports[url] });
    run.unexpected.push(method + ' ' + url);
    return route.fulfill({ status: 500, json: {} });
  });
  return run;
}

const openOutcome = (page, cycleId) => page.goto(preview.base + '/?screen=processing&cycle_id=' + cycleId);
const openCabinet = (page) => page.goto(preview.base + '/?screen=dashboard');
const outcomeButton = (page, name) => page.locator('#processing-panel').getByRole('button', { name, exact: true });
const progress = (page) => page.locator('#processing-outcome-progress');
const notice = (page) => page.locator('#processing-outcome-notice');

async function recordRequests(run, info) {
  expect(run.unexpected).toEqual([]);
  const body = JSON.stringify({ requests: run.calls, report_navigation: run.navigations }, null, 2);
  await info.attach('controlled-http-requests', { body, contentType: 'application/json' });
  if (evidenceDir) {
    await fs.mkdir(evidenceDir, { recursive: true });
    await fs.writeFile(path.join(evidenceDir, info.title.split(' ')[0] + '-http.json'), body + '\n');
  }
}

function saveReport(run, cycleId, reportId, partial) {
  const report = structuredClone(shortProgramReport);
  Object.assign(report, { id: reportId, cycle_id: cycleId, program_name: 'Программа ' + cycleId });
  report.c67.partial_result = partial;
  report.c67.skills[0].presentation.reasons = partial.limitation_reasons || [];
  run.reports[reportPath(reportId)] = report;
  run.reports['/users/assessment/m8/cycles/' + cycleId + '/reports/latest'] = report;
}

function delayed() {
  let release;
  const promise = new Promise((resolve) => { release = resolve; });
  return { promise, release };
}

test('05.1 cabinet, direct URL and a delayed response from A', async ({ page }, info) => {
  const run = await fixture(page);
  await openCabinet(page);
  await cardAction(page, B).click();
  await expect(outcomeTitle(page)).toHaveText('Спасибо за ваши ответы', { timeout: 2000 });
  expect(run.calls).toContain('GET ' + statusPath(B));
  expect(run.calls).not.toContain('GET ' + statusPath(A));

  await openOutcome(page, B);
  await expect(outcomeTitle(page)).toHaveText('Спасибо за ваши ответы');
  expect(new URL(page.url()).searchParams.get('cycle_id')).toBe(B);
  expect(run.calls.filter((call) => call === 'GET ' + statusPath(B))).toHaveLength(2);

  const gate = delayed();
  const answered = delayed();
  run.status[A] = async (route) => {
    await gate.promise;
    try {
      await route.fulfill({ json: { ...ready, cycle_id: A, report_id: 'report-a' } });
    } finally {
      answered.release();
    }
  };
  await outcomeButton(page, 'В личный кабинет').click();
  await cardAction(page, A).click();
  await expect(outcomeTitle(page)).toHaveText('Проверяем завершение оценки');
  await expect.poll(() => run.calls.includes('GET ' + statusPath(A))).toBe(true);
  await outcomeButton(page, 'В личный кабинет').click();
  await cardAction(page, B).click();
  await expect(outcomeTitle(page)).toHaveText('Спасибо за ваши ответы');
  gate.release();
  await answered.promise;
  await expect(outcomeTitle(page)).toHaveText('Спасибо за ваши ответы');
  await expect(outcomeButton(page, 'Посмотреть результат')).toBeHidden();
  expect(new URL(page.url()).searchParams.get('cycle_id')).toBe(B);
  await recordRequests(run, info);
});

test('05.2 ready statuses open the exact full or limited report', async ({ page }, info) => {
  const run = await fixture(page);
  const full = { plan_completed: true, is_incomplete: false, progress: { completed: 3, planned: 3 } };
  const limited = { plan_completed: false, is_incomplete: true, progress: { completed: 1, planned: 3 },
    messages: { title: 'Оценка завершена не полностью' },
    limitation_reasons: [{ code: 'collection_incomplete', message: 'Не все ситуации плана были завершены.' }] };
  run.status[A] = { ...ready, report_id: 'report-a', partial_result: full, route_progress: { completed: 3, total: 3 } };
  run.status[B] = { ...ready, report_id: 'report-b', partial_result: limited, route_progress: { completed: 1, total: 3 } };
  saveReport(run, A, 'report-a', full);
  saveReport(run, B, 'report-b', limited);
  const description = page.locator('#processing-outcome-description');
  await openCabinet(page);
  for (const [cycleId, reportId, copy, count] of [
    [A, 'report-a', 'Вы можете открыть отчёт и радар.', '3 из 3'],
    [B, 'report-b', 'В отчёте указано, какие навыки удалось оценить.', '1 из 3'],
  ]) {
    await cardAction(page, cycleId).click();
    await expect(description).toHaveText(copy);
    await expect(progress(page)).toContainText(count);
    await expect(outcomeTitle(page)).toHaveText('Ваш результат готов');
    const response = page.waitForResponse((value) => new URL(value.url()).pathname === reportPath(reportId));
    await outcomeButton(page, 'Посмотреть результат').click();
    const readback = await response;
    expect(readback.ok()).toBe(true);
    await expect(page.locator('#m8-report-state')).toContainText('Результат готов');
    const selected = new URL(page.url()).searchParams;
    expect(selected.get('report_id')).toBe(reportId);
    expect(selected.get('cycle_id')).toBe(cycleId);
    run.navigations.push({ cycle_id: selected.get('cycle_id'), report_id: selected.get('report_id'), status: readback.status() });
    if (cycleId === A) {
      await page.reload();
      await expect(page.locator('#m8-report-state')).toContainText('Результат готов');
      expect(new URL(page.url()).searchParams.get('report_id')).toBe(reportId);
      await page.locator('#report-back-button').click();
      await expect(page.getByRole('heading', { name: 'Мои оценки', exact: true })).toBeVisible();
      await expect(cardAction(page, B)).toBeVisible();
    }
  }
  await recordRequests(run, info);
});

async function captureOfflineComparison(page) {
  const card = page.locator('#processing-outcome-card');
  const reference = referenceFile ? await page.context().newPage() : null;
  if (evidenceDir) await fs.mkdir(evidenceDir, { recursive: true });
  try {
    for (const width of [1440, 390]) {
      const viewport = { width, height: width === 1440 ? 900 : 844 };
      await page.setViewportSize(viewport);
      for (const element of [outcomeTitle(page), progress(page), notice(page), outcomeButton(page, 'Повторить проверку')]) {
        await expect(element).toBeInViewport({ ratio: 1 });
      }
      expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
      await page.evaluate(() => document.fonts.ready);
      if (evidenceDir) await card.screenshot({ path: path.join(evidenceDir, `returned-offline-product-${width}.png`) });
      if (reference) {
        await reference.setViewportSize(viewport);
        await reference.goto(pathToFileURL(referenceFile).href + '?scene=outcome-offline');
        const referenceCard = reference.locator('.center-card');
        await expect(referenceCard.getByRole('heading')).toHaveText('Готовим результат');
        await expect(referenceCard).toContainText('Не удалось проверить готовность.');
        await expect(referenceCard.getByRole('button', { name: 'Повторить проверку' })).toBeInViewport({ ratio: 1 });
        await reference.evaluate(() => document.fonts.ready);
        if (evidenceDir) await referenceCard.screenshot({ path: path.join(evidenceDir, `returned-offline-reference-${width}.png`) });
      }
    }
  } finally {
    await reference?.close();
  }
}

test('05.3 closing a Cycle, lost read, expiry, processing failure and access denial', async ({ page }, info) => {
  const run = await fixture(page);
  run.journey = { next_action: 'resume_assessment',
    assessment: { runtime_kind: 'cycle', cycle_id: B, status: 'in_progress' } };
  const cycleRoute = '/users/assessment/m7/cycles/' + B;
  const closure = delayed();
  run.handlers[cycleRoute + '/return-state'] = (route) => route.fulfill({ json: { cycle_id: B, allowed_action: 'connected' } });
  run.handlers['/users/assessment/cycles/' + B + '/runtime'] = (route) => route.fulfill({ json: {
    cycle_id: B, status: { collection_status: 'active', remaining_seconds: 1200 }, between_situations: true,
    participant_progress: { planned_total: 8, last_completed_position_no: 2 },
    next_preparation_after: 'as-closed',
    preparation_operation: { operation_id: 'next:as-closed', status: 'completed',
      decision_status: 'NO_ADMISSIBLE_CASE' },
    route: { positions: [], progress: { total_positions: 8, completed_positions: 2 } },
    situations: [], trace: { turns: [], events: [] },
  } });
  run.handlers[cycleRoute + '/completion'] = async (route) => {
    expect(route.request().method()).toBe('POST');
    expect(route.request().postDataJSON().idempotency_key).toBe('complete-after:as-closed');
    await closure.promise;
    await route.fulfill({ json: { cycle_id: B, states: { cycle: 'collection_closed' } } });
  };
  run.status[B] = (route) => route.abort('failed');
  await page.goto(preview.base + '/?screen=interview');
  await expect(outcomeTitle(page)).toHaveText('Проверяем завершение оценки');
  await expect(outcomeButton(page, 'Проверить состояние')).toBeDisabled();
  expect(run.calls).not.toContain('POST ' + cycleRoute + '/next');
  expect(run.calls).not.toContain('GET ' + statusPath(B));
  closure.release();
  await expect(outcomeTitle(page)).toHaveText('Готовим результат');
  await expect(notice(page)).toContainText('Не удалось проверить готовность');
  expect(run.calls).toContain('GET ' + statusPath(B));
  run.status[B] = { ...waiting, close_reason: 'calendar_deadline', route_progress: { completed: 2, total: 8 } };
  await outcomeButton(page, 'Повторить проверку').click();
  await expect(outcomeTitle(page)).toHaveText('Время оценки закончилось');
  await expect(page.locator('#processing-outcome-description')).toContainText('Учтём сохранённые ответы');
  await expect(progress(page)).toContainText('2 из 8');
  await expect(outcomeButton(page, 'Посмотреть результат')).toBeHidden();

  run.status[B] = { ...waiting, report_status: 'limited', report_id: 'report-b',
    processing: { status: 'failed', allowed_actions: [] } };
  const partial = { plan_completed: false, is_incomplete: true, progress: { completed: 1, planned: 3 } };
  saveReport(run, B, 'report-b', partial);
  await outcomeButton(page, 'Проверить готовность').click();
  await expect(outcomeTitle(page)).toHaveText('Не удалось подготовить результат');
  await expect(notice(page)).toContainText('Доступен отчёт с ограничениями');
  const response = page.waitForResponse((value) => new URL(value.url()).pathname === reportPath('report-b'));
  await outcomeButton(page, 'Открыть отчёт с ограничениями').click();
  expect((await response).ok()).toBe(true);
  expect(new URL(page.url()).searchParams.get('cycle_id')).toBe(B);

  run.status[B] = (route) => route.abort('failed');
  await openOutcome(page, B);
  await expect(outcomeTitle(page)).toHaveText('Завершение не подтверждено');
  await expect(outcomeButton(page, 'Посмотреть результат')).toBeHidden();
  run.status[B] = (route) => route.fulfill({ status: 403, json: { detail: 'Нет доступа' } });
  await outcomeButton(page, 'Повторить проверку').click();
  await expect(outcomeTitle(page)).toHaveText('Нет доступа к этой оценке');
  await expect(outcomeButton(page, 'Посмотреть результат')).toBeHidden();
  await expect(outcomeButton(page, 'Открыть отчёт с ограничениями')).toBeHidden();
  expect(run.calls.filter((call) => call.startsWith('POST '))).toEqual(['POST ' + cycleRoute + '/completion']);
  expect(run.calls).not.toContain('GET ' + statusPath(A));
  await test.step('return to B after viewing A, then confirm and open the current report', async () => {
    run.journey = { next_action: 'show_dashboard', report_status: 'ready',
      assessment: { runtime_kind: 'cycle', cycle_id: A, status: 'report_ready' } };
    run.status[A] = { ...ready, report_id: 'report-a', route_progress: { completed: 3, total: 3 } };
    run.status[B] = { ...waiting, route_progress: { completed: 2, total: 8 } };
    await openCabinet(page);
    const visitStart = run.calls.length;
    await cardAction(page, B).click();
    await expect(outcomeTitle(page)).toHaveText('Спасибо за ваши ответы');
    await expect(progress(page)).toHaveText('Завершено ситуаций: 2 из 8.');
    await outcomeButton(page, 'В личный кабинет').click();
    await cardAction(page, A).click();
    await expect(outcomeTitle(page)).toHaveText('Ваш результат готов');
    await expect(progress(page)).toHaveText('Завершено ситуаций: 3 из 3.');
    await outcomeButton(page, 'В личный кабинет').click();

    run.status[B] = (route) => route.abort('failed');
    await cardAction(page, B).click();
    await expect(outcomeTitle(page)).toHaveText('Готовим результат', { timeout: 2000 });
    await expect(progress(page)).toHaveText('Завершено ситуаций: 2 из 8.');
    await expect(notice(page)).toContainText('Не удалось проверить готовность');
    await expect(outcomeButton(page, 'Посмотреть результат')).toBeHidden();
    await expect(outcomeButton(page, 'Открыть отчёт с ограничениями')).toBeHidden();
    expect(run.calls.slice(visitStart).filter((call) => call.endsWith('/status'))).toEqual([
      'GET ' + statusPath(B), 'GET ' + statusPath(A), 'GET ' + statusPath(B),
    ]);
    await captureOfflineComparison(page);

    const retry = delayed();
    const reportId = 'report-b-confirmed';
    const partialResult = { plan_completed: false, is_incomplete: true, progress: { completed: 2, planned: 8 } };
    saveReport(run, B, reportId, partialResult);
    run.status[B] = async (route) => {
      await retry.promise;
      return route.fulfill({ json: { ...ready, cycle_id: B, report_id: reportId,
        route_progress: { completed: 2, total: 8 }, partial_result: partialResult } });
    };
    const retryStart = run.calls.length;
    await outcomeButton(page, 'Повторить проверку').click();
    try {
      await expect.poll(() => run.calls.slice(retryStart)).toEqual(['GET ' + statusPath(B)]);
      await expect(outcomeTitle(page)).toHaveText('Готовим результат');
      await expect(outcomeButton(page, 'Посмотреть результат')).toBeHidden();
    } finally {
      retry.release();
    }
    await expect(outcomeTitle(page)).toHaveText('Ваш результат готов');
    await expect(notice(page)).toBeHidden();
    expect(run.calls.slice(retryStart)).toEqual(['GET ' + statusPath(B)]);
    const reportResponse = page.waitForResponse((value) => new URL(value.url()).pathname === reportPath(reportId));
    await outcomeButton(page, 'Посмотреть результат').click();
    const opened = await reportResponse;
    expect(opened.ok()).toBe(true);
    await expect(page.locator('#m8-report-state')).toHaveText('Результат готов');
    const selected = new URL(page.url()).searchParams;
    expect(selected.get('cycle_id')).toBe(B);
    expect(selected.get('report_id')).toBe(reportId);
    run.navigations.push({ cycle_id: B, report_id: reportId, status: opened.status() });

    await page.locator('#report-back-button').click();
    run.status[B] = (route) => route.abort('failed');
    await cardAction(page, B).click();
    await expect(notice(page)).toContainText('Не удалось проверить готовность');
    await expect(progress(page)).toHaveText('Завершено ситуаций: 2 из 8.');
    await expect(outcomeButton(page, 'Посмотреть результат')).toBeHidden();
  });
  await recordRequests(run, info);
});

test('05.4 unknown, zero and historical progress use the addressed projection', async ({ page }, info) => {
  const run = await fixture(page);
  await openOutcome(page, B);
  await expect(outcomeTitle(page)).toHaveText('Спасибо за ваши ответы');
  await expect(progress(page)).toBeHidden();
  for (const completed of [0, 2]) {
    run.status[B] = { ...waiting, route_progress: { completed, total: 8 } };
    await outcomeButton(page, 'Проверить готовность').click();
    await expect(progress(page)).toHaveText('Завершено ситуаций: ' + completed + ' из 8.');
  }
  run.status[B] = { ...ready, report_id: 'report-b',
    route_progress: { completed: 3, total: 3 }, partial_result: shortProgramReport.c67.partial_result };
  await outcomeButton(page, 'Проверить готовность').click();
  await expect(outcomeTitle(page)).toHaveText('Ваш результат готов');
  await expect(progress(page)).toHaveText('Завершено ситуаций: 3 из 3.');
  await expect(page.locator('#processing-outcome-description')).toContainText('какие навыки удалось оценить');
  await recordRequests(run, info);
});

test('05.5 outcome cards fit the desktop and mobile viewports', async ({ page, context }, info) => {
  const run = await fixture(page);
  if (evidenceDir) await fs.mkdir(evidenceDir, { recursive: true });
  const reference = referenceFile && await context.newPage();
  const card = page.locator('#processing-outcome-card');
  for (const width of [1440, 390]) {
    const viewport = { width, height: width === 1440 ? 900 : 844 };
    await page.setViewportSize(viewport);
    run.status[B] = { ...ready, report_id: 'report-b', route_progress: { completed: 1, total: 8 },
      partial_result: { plan_completed: false, is_incomplete: true } };
    await openCabinet(page);
    await cardAction(page, B).click();
    await expect(outcomeTitle(page)).toHaveText('Ваш результат готов');
    await expect(page.locator('#processing-outcome-description')).toHaveText('В отчёте указано, какие навыки удалось оценить.');
    await expect(progress(page)).toHaveText('Завершено ситуаций: 1 из 8.');
    await expect(outcomeButton(page, 'Посмотреть результат')).toBeInViewport();
    expect((await outcomeButton(page, 'Посмотреть результат').boundingBox()).height).toBeGreaterThanOrEqual(48);
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
    await page.evaluate(() => document.fonts.ready);
    if (evidenceDir) await card.screenshot({ path: path.join(evidenceDir, 'product-limited-' + width + '.png') });
    if (reference) {
      await reference.setViewportSize(viewport);
      await reference.goto(pathToFileURL(referenceFile).href + '?scene=outcome-ready-limited');
      const referenceCard = reference.locator('.center-card');
      await expect(referenceCard).toContainText('В отчёте указано, какие навыки удалось оценить.');
      await expect(referenceCard).toContainText('Завершено ситуаций: 1 из 8.');
      await expect(referenceCard.getByRole('link', { name: 'Посмотреть результат' })).toBeInViewport();
      await reference.evaluate(() => document.fonts.ready);
      if (evidenceDir) await referenceCard.screenshot({ path: path.join(evidenceDir, 'reference-limited-' + width + '.png') });
    }
    run.status[B] = { ...waiting, route_progress: { completed: 2, total: 8 } };
    await openOutcome(page, B);
    await expect(outcomeTitle(page)).toHaveText('Спасибо за ваши ответы');
    await expect(page.locator('#processing-outcome-description')).toBeInViewport();
    if (evidenceDir) await card.screenshot({ path: path.join(evidenceDir, 'product-waiting-' + width + '.png') });
    run.status[B] = (route) => route.abort('failed');
    await outcomeButton(page, 'Проверить готовность').click();
    await expect(outcomeTitle(page)).toHaveText('Готовим результат');
    await expect(notice(page)).toBeInViewport();
    await expect(progress(page)).toContainText('2 из 8');
    if (evidenceDir) await card.screenshot({ path: path.join(evidenceDir, 'product-offline-' + width + '.png') });
    run.status[B] = { ...waiting, results_status: 'failed' };
    await outcomeButton(page, 'Повторить проверку').click();
    await expect(outcomeTitle(page)).toHaveText('Не удалось подготовить результат');
    await expect(page.locator('#processing-outcome-description')).toBeInViewport();
    if (evidenceDir) await card.screenshot({ path: path.join(evidenceDir, 'product-failed-' + width + '.png') });
  }
  await recordRequests(run, info);
});
