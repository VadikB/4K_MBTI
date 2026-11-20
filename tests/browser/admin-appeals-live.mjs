import { chromium } from '@playwright/test';
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
  const answer = adminPage.getByPlaceholder('Ответ участнику');
  await answer.waitFor(); await answer.fill('Синтетическая запись проверена');
  await adminPage.getByRole('button', {name: 'Отправить ответ'}).click();
  await adminPage.getByText('Ответ: Синтетическая запись проверена').waitFor();
  const evidence = await adminPage.evaluate(async () => (await fetch('/__evidence')).json());
  if (evidence.issue?.status !== 'answered' || evidence.issue?.claimed_by_user_id !== 2 ||
      evidence.reply?.author_user_id !== 2 || evidence.reply?.message !== 'Синтетическая запись проверена') {
    throw Error(`database: ${JSON.stringify(evidence)}`);
  }
  const other = await browser.newContext();
  await other.addCookies([{name: 'agent4k_session_token', value: 'other', url: base}]);
  const otherPage = await other.newPage(); await otherPage.goto(base);
  const denied = await otherPage.evaluate(async () => (await fetch('/users/1/acquaintance/issues')).status);
  if (denied !== 403) throw Error(`owner isolation: ${denied}`);
  const newSession = await browser.newContext();
  await newSession.addCookies([{name: 'agent4k_session_token', value: 'participant', url: base}]);
  const readPage = await newSession.newPage(); await readPage.goto(base);
  await readPage.evaluate(async () => {
    const {state} = await import('/web/js/state.js');
    state.pendingUser = {id: 1, full_name: 'Тестовый участник'};
    state.identityEpoch = 1;
    state.dashboard = {current_assessments: [], completed_assessments: []};
    const {openDashboard} = await import('/web/js/screens/dashboard.js');
    openDashboard();
  });
  await readPage.getByRole('heading', {name: 'Ответ по вашему обращению'}).waitFor();
  await readPage.getByText('Синтетическая запись проверена').waitFor();
  await readPage.getByText('Тестовый администратор', {exact: false}).waitFor();
  console.log(JSON.stringify({result: 'PASS', created_id: created.id, issue: evidence.issue, reply: evidence.reply, owner_isolation: denied, participant_readback: true}));
  await Promise.all([participant.close(), admin.close(), other.close(), newSession.close()]);
} finally {
  if (browser) await browser.close();
  if (server.exitCode === null) {
    server.kill('SIGTERM');
    await Promise.race([new Promise(resolve => server.once('exit', resolve)), delay(5000)]);
  }
}
