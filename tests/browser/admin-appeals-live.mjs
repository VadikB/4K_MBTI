import { chromium, expect } from '@playwright/test';
import { spawn } from 'node:child_process';
import { createServer } from 'node:net';
import { setTimeout as delay } from 'node:timers/promises';

if (!process.env.TEST_DATABASE_URL) throw Error('TEST_DATABASE_URL is required');
const portReservation = createServer();
await new Promise(resolve => portReservation.listen(0, '127.0.0.1', resolve));
const port = portReservation.address().port;
await new Promise(resolve => portReservation.close(resolve));
const base = `http://127.0.0.1:${port}`;
const server = spawn(process.env.ADMIN03_PYTHON || 'python3', ['tests/browser/fixtures/admin_appeals_live_server.py'], {
  cwd: process.cwd(), env: {...process.env, PYTHONPATH: process.cwd(), ADMIN03_TEST_PORT: String(port)},
  stdio: ['ignore', 'ignore', 'pipe'],
});
server.stderr.on('data', () => {});
let browser;
try {
  let ready = false;
  for (let attempt = 0; attempt < 100; attempt += 1) {
    if (server.exitCode !== null) throw Error(`HTTP server exited: ${server.exitCode}`);
    try { if ((await fetch(base)).ok) { ready = true; break; } } catch { /* Startup. */ }
    await delay(100);
  }
  if (!ready) throw Error('HTTP server did not become ready');
  browser = await chromium.launch();
  const participant = await browser.newContext();
  await participant.addCookies([{name: 'agent4k_session_token', value: 'participant', url: base}]);
  const participantPage = await participant.newPage();
  const model = {
    readiness: {status: 'ready', organization_id: 10, organization_name: 'Тестовая организация',
      assignment_ref: 'program-a', assignment_id: 11, questionnaire_revision_id: 3,
      briefing: {organizer: 'Тестовая организация', purpose: 'Тестовая цель', results_usage: 'Тестовое использование',
        consent_text: 'Тестовое согласие', consent_version: 1,
        provided_participant_fields: [{key: 'full_name', label: 'ФИО', value: 'Тестовый участник'}],
        questions: ['Рабочие задачи', 'Решения', 'Ограничения']}},
    state: {answers_json: {}}, mandatory_complete: false,
    onboarding: {status: 'not_started', current_step: 0},
    late_readiness: {status: 'waiting_for_assessment_data'},
    assigned_timing: {status: 'resolved', calendar_window_seconds: 172800},
  };
  await participantPage.route('**/users/1/acquaintance', route => route.fulfill({contentType: 'application/json', body: JSON.stringify(model)}));
  await participantPage.route('**/users/1/onboarding', route => {
    model.onboarding = route.request().postDataJSON();
    return route.fulfill({contentType: 'application/json', body: JSON.stringify(model.onboarding)});
  });
  await participantPage.goto(base);
  await participantPage.evaluate(async () => {
    const {state} = await import('/web/js/state.js');
    state.pendingUser = {id: 1, full_name: 'Тестовый участник'};
    state.identityEpoch = 1;
    const {initOnboarding, openOnboarding} = await import('/web/js/screens/onboarding.js');
    initOnboarding(); await openOnboarding();
  });
  await participantPage.getByRole('button', {name: 'Начать знакомство'}).click();
  await participantPage.getByRole('button', {name: 'Сообщить о неточности'}).click();
  await participantPage.getByLabel('Какие сведения нужно проверить?').selectOption('Роль');
  await participantPage.getByLabel('Что нужно уточнить?').fill('Проверьте синтетическую запись');
  await participantPage.locator('#onboarding-dialog').getByRole('button', {name: 'Отправить', exact: true}).click();
  await participantPage.getByText('Сообщение сохранено в вашей организации').waitFor();
  const created = await participantPage.evaluate(async () => (await (await fetch('/users/1/acquaintance/issues')).json()).items[0]);
  if (!created?.id) throw Error(`create: ${JSON.stringify(created)}`);
  const admin = await browser.newContext();
  await admin.addCookies([{name: 'agent4k_session_token', value: 'admin', url: base}]);
  const adminPage = await admin.newPage();
  await adminPage.goto(base);
  await adminPage.evaluate(async () => {
    const {state} = await import('/web/js/state.js');
    state.pendingUser = {id: 2}; state.identityEpoch = 1;
    const dialog = document.createElement('dialog');
    dialog.className = 'admin-member-card-dialog';
    dialog.innerHTML = '<h3>Участник</h3><div data-card-actions></div><button>Закрыть</button>';
    document.body.append(dialog); dialog.showModal();
    const {mountMemberAppeals} = await import('/web/js/screens/admin/appeals.js');
    mountMemberAppeals(dialog, 10, 1);
  });
  await adminPage.getByText('Проверьте синтетическую запись').waitFor();
  await adminPage.getByRole('button', {name: 'Взять в работу'}).click();
  const answer = adminPage.getByLabel('Ответ участнику');
  const send = adminPage.getByRole('button', {name: 'Отправить ответ'});
  const replyPath = '**/users/admin/organizations/10/members/1/issues/' + created.id + '/reply';
  const text = 'Синтетическая запись проверена';
  await answer.waitFor(); await answer.fill(text);
  // The first request never reaches PostgreSQL. The second commits and loses its HTTP response.
  let forwardReply = false;
  let committedStatus;
  let commitError;
  await adminPage.route(replyPath, async route => {
    try {
      if (forwardReply) committedStatus = (await route.fetch({ timeout: 5000 })).status();
    } catch (error) {
      commitError = error;
    } finally {
      await route.abort('failed');
    }
  });
  await send.click();
  await expect(adminPage.getByText('Текст ответа сохранён в форме.', { exact: false })).toBeVisible();
  await expect(answer).toHaveValue(text);
  await expect(send).toBeEnabled();
  const beforeReply = await adminPage.evaluate(async () => (await fetch('/__evidence')).json());
  expect(beforeReply.reply).toBeNull();
  expect(beforeReply.issue.status).toBe('in_progress');

  forwardReply = true;
  await send.click();
  await expect.poll(() => commitError || committedStatus, {timeout: 7000}).toBe(200);
  await expect(adminPage.getByRole('heading', {name: 'Ответ отправлен'})).toBeVisible();
  await expect(adminPage.getByText(text, { exact: true })).toBeVisible();
  await expect(adminPage.locator('.appeal-reply-attribution')).toContainText('Тестовый администратор');
  const savedTime = await adminPage.locator('.appeal-reply-attribution time').textContent();
  const evidence = await adminPage.evaluate(async () => (await fetch('/__evidence')).json());
  if (evidence.issue?.status !== 'answered' || evidence.issue?.claimed_by_user_id !== 2 ||
      evidence.reply?.author_user_id !== 2 || evidence.reply?.message !== text) {
    throw Error(`database: ${JSON.stringify(evidence)}`);
  }
  const other = await browser.newContext();
  await other.addCookies([{name: 'agent4k_session_token', value: 'other', url: base}]);
  const otherPage = await other.newPage(); await otherPage.goto(base);
  const denied = await otherPage.evaluate(async () => (await fetch('/users/1/acquaintance/issues')).status);
  if (denied !== 403) throw Error(`owner isolation: ${denied}`);
  const foreignAdmin = await browser.newContext();
  await foreignAdmin.addCookies([{name: 'agent4k_session_token', value: 'foreign-admin', url: base}]);
  const foreignRead = await foreignAdmin.request.get(base + '/users/admin/organizations/10/members/1/issues');
  expect(foreignRead.status()).toBe(403);
  const newSession = await browser.newContext({timezoneId: 'America/Los_Angeles'});
  await newSession.addCookies([{name: 'agent4k_session_token', value: 'participant-reentry', url: base}]);
  const readPage = await newSession.newPage();
  const assessmentName = 'Синтетическая оценка 4К';
  await readPage.route('**/users/1/acquaintance', route => route.fulfill({ json: {
    ...model, assignment_id: model.readiness.assignment_id, assessment_name: assessmentName,
  } }));
  await readPage.goto(base);
  await readPage.evaluate(async () => {
    const {state} = await import('/web/js/state.js');
    state.pendingUser = {id: 1, full_name: 'Тестовый участник'};
    state.identityEpoch = 1;
    state.dashboard = {current_assessments: [], completed_assessments: []};
    const {openDashboard} = await import('/web/js/screens/dashboard.js');
    openDashboard();
  });
  await readPage.getByRole('heading', {name: 'Ответ по вашему обращению'}).waitFor();
  await readPage.getByText(text).waitFor();
  await readPage.getByText('Тестовый администратор', {exact: false}).waitFor();
  await readPage.locator('.participant-appeal').getByText(assessmentName, {exact: true}).waitFor();
  await expect(readPage.locator('.participant-appeal time')).toHaveText(savedTime);
  await readPage.getByText('Ваше обращение', {exact: true}).click();
  await readPage.getByText('Поле: Роль\nПроверьте синтетическую запись', {exact: true}).waitFor();
  const attribution = await readPage.locator('.participant-appeal small').innerText();
  if (!/Тестовый администратор · \d{2}\.\d{2}\.\d{4}/.test(attribution)) {
    throw Error(`Missing saved reply attribution/time: ${attribution}`);
  }
  console.log(JSON.stringify({result: 'PASS', created_id: created.id, issue: evidence.issue, reply: evidence.reply,
    owner_isolation: denied, tenant_isolation: foreignRead.status(), participant_readback: true,
    failed_save_keeps_draft: true, saved_reply_readback_after_lost_response: true}));
  await Promise.all([participant.close(), admin.close(), other.close(), foreignAdmin.close(), newSession.close()]);
} finally {
  if (browser) await browser.close();
  if (server.exitCode === null) {
    server.kill('SIGTERM');
    await Promise.race([new Promise(resolve => server.once('exit', resolve)), delay(5000)]);
  }
}
