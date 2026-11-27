import { expect, test } from '@playwright/test';
import fs from 'node:fs/promises';
import path from 'node:path';
import { startAdminProgramPreview } from '../../scripts/adm-program-ui-preview.mjs';

const inputDir = process.env.TASK6_BROWSER_INPUTS;
const baselineRoot = process.env.TASK6_BASE_ROOT;
const artifactDir = process.env.TASK6_BROWSER_EVIDENCE;
const answerMessage = 'Ответ сохранён, но обработать его не удалось. Отправлять ответ повторно не нужно. Обратитесь к администратору оценки.';
const reportMessage = 'Прохождение завершено. Не удалось сформировать итоговый отчёт.';
const answerTitle = 'Не удалось обработать ответ участника';
const answerDetail = 'Ответ сохранён. Прохождение остановилось на обработке ответа в текущей ситуации';
const reportTitle = 'Не удалось сформировать итоговый отчёт';
const reportDetail = 'Сбор ответов завершён. Ошибка возникла при подготовке отчёта';
const unknown = 'Произошла ошибка обработки. Подробности пока недоступны';
const readError = 'Не удалось обновить состояние';
const progress = 'Завершено 0 из 8 ситуаций.';

test.setTimeout(35000);
test.skip(!inputDir, 'Requires the synthetic HTTP snapshots exported by test_task6_processing_status_db.py');

const baseOf = preview => 'http://127.0.0.1:' + preview.server.address().port;

async function capture(locator, file) {
  if (!artifactDir) return;
  await fs.mkdir(artifactDir, { recursive: true });
  await locator.screenshot({ path: path.join(artifactDir, file + '.png'), animations: 'disabled' });
}

async function replay(page, fixture, { admin = false, closed = false } = {}) {
  const id = admin ? 88 : fixture.participant;
  const user = { id, email: 'task6@example.test', full_name: admin ? 'Администратор оценки' : 'Синтетический участник' };
  const organization = fixture.registry.items.find(item => item.id === fixture.org);
  const registry = structuredClone(fixture.registry);
  const selected = registry.items.find(item => item.id === fixture.org);
  if (closed) selected.assessment_program.assignment_ref = fixture.secondAssessment;
  const cycle = fixture.runtime.cycle_id;
  const asId = fixture.runtime.current_situation.assessment_situation_id;
  const flow = { runtime: fixture.runtime, status: fixture.report, registry, failedRead: false, requests: [] };
  await page.route('**/users/**', async (route) => {
    const request = route.request();
    const pathname = new URL(request.url()).pathname;
    flow.requests.push([request.method(), pathname]);
    const json = (value) => route.fulfill({ json: value });
    if (pathname === '/users/version') return json({ version: '2.1.85 · синтетический сценарий' });
    if (['/users/session/restore', '/users/' + id + '/session-bootstrap'].includes(pathname)) {
      return json({ authenticated: true, user, is_admin: admin, dashboard: {}, admin_dashboard: { is_superadmin: false } });
    }
    if (pathname.endsWith('/journey-state')) return json({ next_action: 'resume_assessment',
      assessment: { runtime_kind: 'cycle', cycle_id: cycle, assessment_situation_id: asId, status: 'active' },
      profile: { status: 'complete' }, onboarding: { status: 'completed' } });
    if (pathname.endsWith('/return-state')) return json({ cycle_id: cycle, allowed_action: 'connected' });
    if (pathname.endsWith('/runtime')) return flow.failedRead ? route.abort('failed') : json(flow.runtime);
    if (pathname === '/users/assessment/m8/cycles/' + fixture.report.cycle_id + '/status') {
      return flow.failedRead ? route.abort('failed') : json(flow.status);
    }
    if (pathname.endsWith('/presence')) return json({ heartbeat_interval_seconds: 10 });
    if (pathname.endsWith('/draft')) return json({ owner_id: String(id), cycle_id: cycle,
      assessment_situation_id: asId, version: 0, revision: '', text: '' });
    if (pathname === '/users/admin/organizations') return json(flow.registry);
    if (pathname.endsWith('/assessment-program')) return json({ connection: selected.assessment_program });
    if (pathname.endsWith('/questionnaire') || pathname.endsWith('/issues')) return json({ items: [] });
    if (pathname === '/users/admin/dashboard') return json({ is_superadmin: false });
    if (pathname.endsWith('/answer-status')) return json({ status: 'absent' });
    if (pathname === '/users/admin/organizations/' + organization.id) return json(selected);
    return json({});
  });
  return flow;
}

async function memberSurface(browser, preview, fixture, label, detail, name, { closed = false, baseline = false } = {}) {
  const page = await browser.newPage();
  try {
    const flow = await replay(page, fixture, { admin: true, closed });
    await page.goto(baseOf(preview) + '/?screen=admin-organizations');
    const row = page.locator(`[data-organization-id="${fixture.org}"] [data-member-user-id="${fixture.participant}"]`);
    const stage = row.locator('.admin-organization-current-stage');
    const stageDetail = row.locator('.admin-organization-member-stage > span').last();
    const openDetails = row.getByRole('button', { name: 'Подробнее об обработке' });
    await expect(stage).toHaveText(label);
    if (!baseline) {
      await expect(openDetails).toHaveAttribute('data-assignment-id', String(closed ? fixture.reportAssignmentId : 33));
      if (!closed) await expect(stageDetail).toHaveText(progress);
    }
    const rendered = { stage: await stage.innerText(), progress: await stageDetail.innerText() };
    await capture(row, name + '-row');
    await openDetails.click();
    const dialog = page.getByRole('dialog', { name: baseline ? 'Ошибка обработки результата' : label });
    const heading = dialog.getByRole('heading');
    const description = dialog.locator('[data-processing-description]');
    await expect(description).toHaveText(detail);
    rendered.title = await heading.innerText();
    rendered.detail = await description.innerText();
    const check = dialog.getByRole('button', { name: 'Проверить состояние', exact: true });
    const registryReads = () => flow.requests.filter(([, url]) => url === '/users/admin/organizations');
    if (baseline) {
      await expect(dialog).toContainText('Отчёт можно открыть только после готовности и при наличии права просмотра.');
    } else {
      await expect(dialog).not.toContainText(/прав[оае] просмотра|Номер обращения|Номер случая/);
      await expect(dialog.getByRole('button', { name: /Повторить|Восстановить/ })).toHaveCount(0);
      const readsBefore = registryReads().length;
      await check.click();
      await expect(dialog.getByRole('status')).toHaveText('Состояние обновлено.');
      expect(registryReads().slice(readsBefore)).toEqual([['GET', '/users/admin/organizations']]);
      await expect(stage).toHaveText(label);
      if (!closed) await expect(stageDetail).toHaveText(progress);
    }
    await capture(dialog, name + '-details');
    if (!baseline && !closed) {
      flow.registry = fixture.recoveredRegistry;
      const readsBefore = registryReads().length;
      await check.click();
      await expect(stage).toHaveText('Оценка выполняется');
      await expect(stageDetail).toHaveText(progress);
      await expect(dialog).toHaveCount(0);
      await expect(openDetails).toHaveCount(0);
      expect(registryReads().slice(readsBefore)).toEqual([['GET', '/users/admin/organizations']]);
      rendered.recovered = { stage: await stage.innerText(), progress: await stageDetail.innerText() };
      await capture(row, name + '-recovered-row');
    }
    expect(flow.requests.filter(([method]) => method !== 'GET')).toEqual([]);
    return rendered;
  } finally {
    await page.close();
  }
}

for (const broken of ['evidence', 'assessment']) {
  test(`Задание 6 · назначение №33, восстановление и сбой отчёта · M6 ${broken}`, async ({ browser }, info) => {
    const fixture = JSON.parse(await fs.readFile(path.join(inputDir, broken + '.json'), 'utf8'));
    expect(fixture.assignmentId).toBe(33);
    const preview = await startAdminProgramPreview({ port: 0, adapter: async ({ url, response }) => {
      if (url.pathname !== '/') return false;
      response.setHeader('Content-Type', 'text/html; charset=utf-8');
      response.end(await fs.readFile('web/index.html'));
      return true;
    } });
    try {
      const page = await browser.newPage();
      const flow = await replay(page, fixture);
      await page.goto(baseOf(preview) + '/?screen=interview');
      const interview = page.locator('#interview-error');
      const input = page.locator('#interview-textarea');
      const check = interview.getByRole('button', { name: 'Проверить состояние', exact: true });
      const runtimePath = '/users/assessment/cycles/' + fixture.runtime.cycle_id + '/runtime';
      const checkRuntime = async () => {
        const read = page.waitForResponse(response => new URL(response.url()).pathname === runtimePath);
        await check.click();
        const response = await read;
        expect(response.status()).toBe(200);
        expect(response.request().method()).toBe('GET');
      };
      const savedTurn = page.locator(`#interview-messages [data-turn-id="${fixture.turnId}"]`);
      await expect(interview).toContainText(answerMessage);
      const renderedAnswer = await interview.evaluate(node => node.firstChild.textContent.trim());
      expect(renderedAnswer).toBe(answerMessage);
      await expect(savedTurn).toHaveCount(1);
      const savedAnswer = fixture.runtime.trace.turns.find(turn => turn.turn_id === fixture.turnId).content_text;
      await expect(savedTurn).toHaveAttribute('data-message-text', savedAnswer);
      await expect(input).toBeDisabled();
      await expect(input).toHaveAttribute('placeholder', '');
      await capture(page.locator('#interview-panel'), broken + '-after-participant-answer');
      await expect(interview.getByRole('button', { name: /Повторить|Восстановить/ })).toHaveCount(0);
      await checkRuntime();
      await expect(interview).toContainText(answerMessage);
      await expect(savedTurn).toHaveCount(1);
      flow.failedRead = true;
      await check.click();
      await expect(interview).toContainText(readError);
      flow.failedRead = false;
      flow.runtime = fixture.unknown;
      await check.click();
      await expect(interview).toContainText(unknown);
      await expect(interview).not.toContainText('Ответ сохранён');
      flow.runtime = fixture.waiting;
      await check.click();
      await expect(interview).toContainText('Ответ сохранён. Идёт обработка');
      // Return to the confirmed failure before showing the real post-worker response.
      flow.runtime = fixture.runtime;
      await checkRuntime();
      await expect(interview).toContainText(answerMessage);
      flow.runtime = fixture.success;
      await checkRuntime();
      const finish = page.getByRole('button', { name: 'Завершить ситуацию', exact: true });
      await expect(finish).toBeVisible();
      await expect(finish).toBeEnabled();
      await expect(interview).not.toContainText(answerMessage);
      await expect(interview).not.toContainText(unknown);
      await expect(savedTurn).toHaveCount(1);
      await expect(savedTurn).toHaveAttribute('data-message-text', savedAnswer);
      await expect(savedTurn.getByRole('button', { name: 'Повторить', exact: true })).toHaveCount(0);
      const renderedFinish = await finish.innerText();
      const renderedTurnCount = await savedTurn.count();
      await capture(page.locator('#interview-panel'), broken + '-participant-answer-recovered');

      await page.goto(baseOf(preview) + '/?screen=processing&cycle_id=' + fixture.report.cycle_id);
      const outcome = page.locator('#processing-outcome-card');
      const title = outcome.getByRole('heading');
      const outcomeCheck = outcome.getByRole('button', { name: 'Проверить состояние', exact: true });
      await expect(title).toHaveText(reportMessage);
      const renderedReport = await title.innerText();
      await capture(outcome, broken + '-after-participant-report');
      await expect(outcome.getByRole('button', { name: /Посмотреть результат|Повторить|Восстановить/ })).toHaveCount(0);
      flow.status = fixture.calculation;
      await outcomeCheck.click();
      await expect(title).toHaveText('Не удалось рассчитать итоговый результат');
      flow.status = fixture.ready;
      await outcomeCheck.click();
      await expect(outcome).toContainText(reportMessage);
      await expect(outcome).toContainText('Доступна сохранённая версия отчёта.');
      await expect(outcome.getByRole('button', { name: 'Посмотреть результат' })).toBeVisible();
      expect(flow.requests.filter(([method, url]) => method !== 'GET' && !url.endsWith('/presence'))).toEqual([]);
      await page.close();

      const { recovered: adminAfterRecovery, ...adminAnswer } =
        await memberSurface(browser, preview, fixture, answerTitle, answerDetail, broken + '-after-admin-answer');
      const adminReport = await memberSurface(browser, preview, fixture, reportTitle, reportDetail, broken + '-after-admin-report', { closed: true });
      const rendered = {
        assignment: fixture.assignmentId,
        answer: { participant: renderedAnswer, admin: adminAnswer },
        afterRecovery: { participantAction: renderedFinish, savedTurnCount: renderedTurnCount, admin: adminAfterRecovery },
        report: { assignment: fixture.reportAssignmentId, participant: renderedReport, admin: adminReport },
      };
      const json = JSON.stringify(rendered, null, 2) + '\n';
      await info.attach('rendered-texts', { body: json, contentType: 'application/json' });
      if (artifactDir) await fs.writeFile(path.join(artifactDir, broken + '-rendered-texts.json'), json);
    } finally {
      await preview.close();
    }
  });
}

test('Задание 6 · исходный интерфейс 2.1.85 на тех же HTTP-снимках', async ({ browser }) => {
  test.skip(!baselineRoot, 'Optional comparison to the checked-out baseline bundle');
  const fixture = JSON.parse(await fs.readFile(path.join(inputDir, 'evidence.json'), 'utf8'));
  const preview = await startAdminProgramPreview({ root: baselineRoot, port: 0, adapter: async ({ url, response }) => {
    if (url.pathname !== '/') return false;
    response.setHeader('Content-Type', 'text/html; charset=utf-8');
    response.end(await fs.readFile(path.join(baselineRoot, 'web/index.html')));
    return true;
  } });
  try {
    const page = await browser.newPage();
    const flow = await replay(page, fixture);
    const { cycle_id: cycleId, failed_answer_turn_id: turnId, current_situation: situation } = fixture.runtime;
    const situationId = situation.assessment_situation_id;
    const text = fixture.runtime.trace.turns.find(turn => turn.turn_id === turnId).content_text;
    const ownerId = String(fixture.participant);
    // Reproduce the receipt held by the original tab after the successful POST.
    await page.addInitScript(({ key, operation }) => sessionStorage.setItem(key, JSON.stringify(operation)), {
      key: `agent4k.assessmentPending:${cycleId}:${situationId}:${ownerId}`,
      operation: { cycleId, situationId, ownerId, turnId, text, draftValue: text, status: 'saved', accepted: true,
        requestId: 'task6-answer', clarificationId: null,
        sourcePhase: JSON.stringify(['active', null, null, null, null]),
        endpoint: `/users/assessment/m5/situations/${situationId}/turns` },
    });
    flow.status = { ...fixture.report, processing: { ...fixture.report.processing,
      message: 'Не удалось завершить техническую обработку. Сохранённые ответы не потеряны.' } };
    await page.goto(baseOf(preview) + '/?screen=interview');
    await expect(page.locator('#interview-error')).toContainText('Ответ сохранён. Не удалось завершить обработку.');
    await expect(page.locator('#interview-textarea')).toHaveAttribute('placeholder', 'Дождитесь завершения обработки');
    await capture(page.locator('#interview-panel'), 'before-participant-answer');
    await page.goto(baseOf(preview) + '/?screen=processing&cycle_id=' + fixture.report.cycle_id);
    const outcome = page.locator('#processing-outcome-card');
    await expect(outcome.getByRole('heading')).toHaveText('Не удалось подготовить результат');
    await expect(outcome).toContainText('Ваши ответы сохранены.');
    await capture(outcome, 'before-participant-report');
    await page.close();
    const title = 'Не удалось обработать результат';
    const detail = 'Результат пока недоступен.';
    await memberSurface(browser, preview, fixture, title, detail, 'before-admin-answer', { baseline: true });
    await memberSurface(browser, preview, fixture, title, detail, 'before-admin-report', { baseline: true, closed: true });
  } finally {
    await preview.close();
  }
});
