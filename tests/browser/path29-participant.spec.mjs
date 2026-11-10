import { test, expect } from '@playwright/test';
import { spawn, spawnSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { createHash, randomUUID } from 'node:crypto';
import { persistReceipt, isTerminalPreparationReceipt } from './fixtures/receipt-file.mjs';
import { verifyPreparation, verifyFirstCase, verifyPublishedProgram } from './fixtures/preparation-receipt.mjs';
import { capturePathViewports } from './fixtures/path-viewports.mjs';
import { waitForPasswordCreationForm } from './fixtures/auth-password-form.mjs';
import { captureFailurePage } from './fixtures/failure-page.mjs';
import { completeStartedAssessment, readExecutionExport, terminalExecutionKnown } from './fixtures/assessment-completion-profile.mjs';

function canonical(value) {
  if (Array.isArray(value)) return '[' + value.map(canonical).join(',') + ']';
  if (value !== null && typeof value === 'object') return '{' + Object.keys(value).sort()
    .map((key) => JSON.stringify(key) + ':' + canonical(value[key])).join(',') + '}';
  return JSON.stringify(value);
}
// Participant payload/snapshot refs use m5_case_runtime's JSON + LF contract.
const checksum = (value) => createHash('sha256').update(canonical(value) + '\n').digest('hex');

test('PATH29 owned backend: invitation → scoped chat → durable preparation → explicit first case', async ({ browser }) => {
  test.setTimeout(process.env.P4K_REAL_PROVIDER === '1' ? 900000 : 240000);
  if (!process.env.STAND_ADMIN_URL) throw new Error('Explicit isolated STAND_ADMIN_URL required');
  const root = process.cwd(), python = process.env.BROWSER_PYTHON || path.join(root, '.venv/bin/python');
  const evidenceRoot = process.env.P4K_EVIDENCE_DIRECTORY || path.join(root, '.test-stand/path29');
  const dir = path.join(evidenceRoot, randomUUID());
  fs.mkdirSync(dir, { recursive: true });
  const port = process.env.P4K_PORT || '18859';
  const statePath = path.join(dir, 'state.json'), base = 'http://127.0.0.1:' + port;
  const fullPath = process.env.P4K_FULL_PATH === '1';
  const realProvider = process.env.P4K_REAL_PROVIDER === '1';
  const compositeProfile = process.env.P4K_COMPLETION_PROFILE === '1';
  const requestedRelease = process.env.P4K_PUBLISHED_RELEASE_REF
    ? JSON.parse(process.env.P4K_PUBLISHED_RELEASE_REF) : undefined;
  if (fullPath && !realProvider) throw new Error('FULL_PATH_REQUIRES_EXPLICIT_REAL_PROVIDER');
  if (realProvider) test.info().annotations.push({ type: 'llm', description: 'Explicit real DeepSeek synthetic diagnostic' });
  const run = (script, args) => {
    const result = spawnSync(python, [script, ...args], { encoding: 'utf8', timeout: 180000 });
    if (result.status !== 0) throw new Error(script + ': ' + result.stderr + result.stdout);
  };
  const cli = (action) => run('scripts/test_stand.py', [action, '--state', statePath, '--port', port,
    '--gateway', realProvider ? '0' : '1', '--provider', realProvider ? 'real' : 'disabled']);
  const superContext = await browser.newContext(), adminContext = await browser.newContext(), participantContext = await browser.newContext();
  const extraContexts = [];
  const superPage = await superContext.newPage(), admin = await adminContext.newPage(), page = await participantContext.newPage();
  let activePage = superPage;
  let activeActor = 'superadmin';
  let server;
  let finalReceipt;
  let terminalReceiptFile = 'first-case-receipt.json';
  let runId;
  let scenarioCompleted = false;
  let step = 'create_owned_database';
  let preparationReceiptRequired = false;
  let terminalPreparationReceiptSaved = false;
  let executionStarted = false;
  let executionCycleId;
  const save = (name, value) => persistReceipt(path.join(dir, name + '.json'), value);
  cli('create');
  try {
    const initialState = JSON.parse(fs.readFileSync(statePath, 'utf8'));
    runId = initialState.run_id;
    save('run', { run_id: initialState.run_id, database: initialState.database, port,
      provider_mode: initialState.provider_mode,
      profile: compositeProfile ? 'assessment-execution-contour/2' : 'assessment-first-case/1.1',
      program_source: fullPath ? process.env.P4K_PROGRAM_SOURCE : undefined,
      published_release_ref: fullPath ? requestedRelease : undefined,
      code: process.env.P4K_CODE_IDENTITY ? JSON.parse(process.env.P4K_CODE_IDENTITY) : null });
    initialState.browser_case = 'specialist';
    if (!fullPath && !realProvider) {
      initialState.component_plan_fixture = 'browser-component-plan-boundary/1';
      test.info().annotations.push({type:'synthetic_upstream',description:
        'Static component only: upstream plan policy substituted, NOT human/pilot admission or full PATH; AS/start/time checks remain real'});
      save('component-boundary', {fixture:initialState.component_plan_fixture,
        product_admission_evidence:false, full_path:false, provider_mode:'disabled'});
    }
    fs.writeFileSync(statePath, JSON.stringify(initialState));
    cli('bootstrap');
    run('tests/path29_browser_inputs.py', ['--state', statePath]);
    const state = JSON.parse(fs.readFileSync(statePath, 'utf8'));
    const selectedRelease = state.path29.published_release_ref;
    if (fullPath && state.path29.input_mode === 'published-pilot') {
      expect(selectedRelease).toBeTruthy();
      if (requestedRelease) {
        expect(selectedRelease.sha256).toBe(requestedRelease.sha256);
        expect(selectedRelease.program).toEqual(requestedRelease.program);
      }
      save('run', { ...JSON.parse(fs.readFileSync(path.join(dir, 'run.json'), 'utf8')),
        program_source: 'published-pilot', published_release_ref: selectedRelease });
    }
    step = 'superadmin_create_organization';
    const fd = fs.openSync(path.join(dir, 'server.log'), 'a');
    server = spawn(python, ['tests/path29_browser_server.py', '--state', statePath], { stdio: ['ignore', fd, fd] });
    fs.closeSync(fd);
    await expect.poll(async () => { try { return (await fetch(base + '/health/ready')).status; } catch { return 0; } }, { timeout: 30000 }).toBe(200);
    const snapshot = async () => (await page.request.get(base + '/__pytest__/participant-state')).json();
    expect(await snapshot()).toEqual({ profiles: 0, cycles: 0, started: 0, operations: 0 });
    if (fullPath) {
      await superPage.goto(base);
      await superPage.locator('#email-input').fill('superadmin@example.test');
      await superPage.locator('#request-magic-link-button').click();
      await superPage.locator('#magic-token-input').fill(state.password);
      await superPage.locator('#verify-magic-link-button').click();
      await superPage.getByRole('button', { name: 'Организации', exact: true }).click();
      await expect(superPage.locator('#admin-organizations-panel')).toBeVisible();
      await superPage.locator('#admin-organization-name-input').fill('Сквозная организация PATH29');
      await superPage.locator('#admin-organization-code-input').fill('path29_full_' + state.run_id.slice(0, 8));
      const created = superPage.waitForResponse((response) => response.request().method() === 'POST' && response.url().endsWith('/users/admin/organizations'));
      await superPage.locator('#admin-organization-create-button').click();
      expect((await created).status()).toBe(200);
      const organizations = await (await superPage.request.get(base + '/users/admin/organizations')).json();
      const target = organizations.items.find((item) => item.code === 'path29_full_' + state.run_id.slice(0, 8));
      expect(target).toBeTruthy(); state.path29.organization_id = target.id;
      await superPage.locator('#admin-organization-select').selectOption(String(target.id));
      const superCard = superPage.locator(`[data-organization-id="${target.id}"]`);
      await expect(superCard).toBeVisible();
      await superCard.locator('select[name="program_definition_id"]').selectOption(String(state.path29.program_id));
      await capturePathViewports(superPage, dir, 'superadmin-program', [
        { name: 'program', locator: superCard.locator('select[name="program_definition_id"]') },
        { name: 'connect', locator: superCard.locator('form[data-action="connect-assessment-program"]').getByRole('button', { name: 'Подключить' }) },
      ]);
      await superCard.locator('form[data-action="connect-assessment-program"]').getByRole('button', { name: 'Подключить' }).click();
      await expect(superCard.locator('form[data-action="connect-assessment-program"]')).toContainText('Подключено:');
      const addAdmin = superCard.locator('form[data-action="add-admin"]');
      await addAdmin.locator('input[type="email"]').fill(state.path29.admin_email);
      await addAdmin.getByRole('button', { name: 'Добавить' }).click();
      await expect(superCard).toContainText(state.path29.admin_email);
    }
    step = 'admin_login_questionnaire_and_assignment';
    activePage = admin;
    activeActor = 'administrator';
    await admin.goto(base);
    await admin.locator('#email-input').fill(state.path29.admin_email);
    await admin.locator('#request-magic-link-button').click();
    if (fullPath) {
      await expect.poll(async () => (await (await superPage.request.get(base + '/__pytest__/mailbox', {
        params: { email: state.path29.admin_email, purpose: 'email_verification' },
      })).json()).item !== null).toBe(true);
      const adminMail = await (await superPage.request.get(base + '/__pytest__/mailbox', {
        params: { email: state.path29.admin_email, purpose: 'email_verification' },
      })).json();
      const login = new URL(adminMail.item.action_url);
      await admin.goto(base + '/' + login.search);
      await waitForPasswordCreationForm(admin, state.path29.admin_email);
      await admin.locator('#magic-token-input').fill(state.password);
      await admin.locator('#verify-magic-link-button').click();
      await expect(admin.locator('#auth-credential-step-indicator')).toHaveText('Шаг 2 из 2');
      await admin.locator('#magic-token-input').fill(state.password);
      await admin.locator('#verify-magic-link-button').click();
    } else {
      await admin.locator('#magic-token-input').fill(state.password);
      await admin.locator('#verify-magic-link-button').click();
    }
    await expect(admin.locator('#admin-organizations-panel')).toBeVisible();
    const card = admin.locator(`[data-organization-id="${state.path29.organization_id}"]`);
    await card.getByRole('button', { name: 'Данные организации', exact: true }).click();
    const form = card.locator('[data-action="preview-early-data"]');
    await expect(form.locator('[name="assignment_ref"]')).toHaveAttribute('type', 'hidden');
    await expect(form.locator('[name="assignment_ref"]')).toHaveValue(state.path29.assignment_ref || 'PATH29 browser');
    const values = { source_author: 'Синтетический заказчик',
      organization_name: 'Синтетическая организация PATH29', organization_type: 'Компания', industry: 'ИТ',
      activity_description: 'Синтетическая проверка пути участника', purpose: 'Синтетическая цель развития',
      results_usage: 'Для синтетического плана развития', result_recipients: 'Участник', organizer: 'Синтетический HR',
      responsible_contact: state.path29.admin_email, case_reality_level: 'Реальные', organization_name_usage_rules: 'Разрешено' };
    for (const [name, value] of Object.entries(values)) {
      if (name !== 'source_author') await form.locator(`[name="${name}"]`).fill(value);
    }
    await capturePathViewports(admin, dir, 'admin-questionnaire', [
      { name: 'responsible-contact', locator: form.locator('[name="responsible_contact"]') },
      { name: 'purpose', locator: form.locator('[name="purpose"]') },
      { name: 'preview', locator: form.getByRole('button', { name: 'Сохранить черновик и предпросмотр' }) },
    ]);
    await form.getByRole('button', { name: 'Сохранить черновик и предпросмотр' }).click();
    await card.locator('.admin-questionnaire-preview').getByRole('button', { name: 'Подтвердить сведения' }).click();
    await expect(card.locator('.admin-questionnaire-confirmation')).toContainText('Сведения подтверждены');
    if (state.path29.input_mode === 'published-pilot') {
      // A failed GET is not evidence that the already committed questionnaire
      // became unconfirmed. Exercise the actual built entry before any LLM cost.
      step = 'ps02_confirmed_questionnaire_read_error';
      const questionnaireUrl = `**/users/admin/organizations/${state.path29.organization_id}/questionnaire`;
      await admin.route(questionnaireUrl, (route) => route.fulfill({ status: 503,
        contentType: 'application/json', body: JSON.stringify({ detail: 'Synthetic readback temporarily unavailable' }) }));
      await admin.reload();
      await expect(card).toBeVisible();
      await card.getByRole('button', { name: 'Участники оценки', exact: true }).click();
      await expect(card.locator('.admin-questionnaire-load-state.error').first()).toBeAttached();
      const readiness = card.locator('.admin-assignment-readiness');
      save('ps02-read-error', { organization_id: state.path29.organization_id,
        assignment_ref: state.path29.assignment_ref, confirmed_before_reload: true,
        injected_failure: 'GET questionnaire HTTP 503; no write',
        actual_readiness: await readiness.innerText() });
      await admin.screenshot({ path: path.join(dir, 'ps02-read-error.png'), fullPage: true });
      await expect(readiness).not.toContainText('Анкета для выбранной оценки не подтверждена');
      await expect(readiness).not.toContainText('Можно назначать');
      await admin.unroute(questionnaireUrl);
      await card.getByRole('button', { name: 'Данные организации', exact: true }).click();
      await card.getByRole('button', { name: 'Повторить', exact: true }).filter({ visible: true }).click();
      await card.getByRole('button', { name: 'Участники оценки', exact: true }).click();
      await expect(readiness).toContainText('Можно назначать');
    }
    await card.getByRole('button', { name: 'Участники оценки', exact: true }).click();
    const add = card.locator('[data-action="add-member"]');
    const fullName = 'Синтетический Участник С Очень Длинным Именем Для Проверки Переноса Строк';
    const position = 'Синтетический специалист по согласованию неоднозначных задач нескольких подразделений';
    await add.locator('[name="email"]').fill(state.path29.participant_email);
    await add.locator('[name="full_name"]').fill(fullName);
    await add.locator('[name="role_description"]').fill(position);
    await add.getByRole('button', { name: 'Добавить', exact: true }).click();
    await expect(add.locator('[data-operation-status]')).toContainText('Участник привязан');
    const checkbox = card.locator(`input[name="invitation_email"][value="${state.path29.participant_email}"]`);
    await checkbox.check();
    await capturePathViewports(admin, dir, 'admin-assignment', [
      { name: 'long-participant-selection', locator: checkbox },
      { name: 'assign', locator: card.getByRole('button', { name: 'Назначить оценку', exact: true }) },
    ]);
    await card.getByRole('button', { name: 'Назначить оценку', exact: true }).click();
    await expect(card.locator('[data-assignment-sources]')).toHaveCount(0);
    await expect(card.locator('[data-operation-status]').first()).toContainText(`${fullName}: оценка назначена.`);
    await checkbox.check();
    await card.getByRole('button', { name: 'Отправить приглашения', exact: true }).click();
    await expect.poll(async () => (await (await admin.request.get(base + '/__pytest__/mailbox', {
      params: { email: state.path29.participant_email, purpose: 'organization_invitation' },
    })).json()).item !== null).toBe(true);
    const mail = await (await admin.request.get(base + '/__pytest__/mailbox', {
      params: { email: state.path29.participant_email, purpose: 'organization_invitation' },
    })).json();
    expect(mail.item).toBeTruthy();
    const invitation = new URL(mail.item.action_url);
    expect(invitation.origin).toBe('https://test.example.com');
    step = 'participant_login_and_acquaintance';
    activePage = page;
    activeActor = 'participant';
    await page.goto(base + '/' + invitation.search);
    await waitForPasswordCreationForm(page, state.path29.participant_email);
    await page.locator('#magic-token-input').fill(state.password);
    await page.locator('#verify-magic-link-button').click();
    await expect(page.locator('#auth-credential-step-indicator')).toHaveText('Шаг 2 из 2');
    await page.locator('#magic-token-input').fill(state.password);
    await page.locator('#verify-magic-link-button').click();
    await expect(page.locator('#onboarding-panel')).toBeVisible();
    const participantId = (await (await page.request.get(base + '/users/session/restore')).json()).user.id;
    const savedAcquaintance = async () => (await page.request.get(`${base}/users/${participantId}/acquaintance`)).json();
    const next = page.locator('#onboarding-next');
    await next.click();
    await expect(page.locator('#feature-list')).toContainText(fullName);
    await expect(page.locator('#feature-list')).toContainText(position);
    await expect(page.locator('#feature-list select')).toHaveCount(0);
    await expect(page.locator('#onboarding-skip')).toBeHidden();
    await next.click();
    const answer = page.locator('.onboarding-answer');
    const saveAnswer = async (value) => {
      const previousQuestion = await page.locator('#onboarding-title').innerText();
      await answer.fill(value);
      const saved = page.waitForResponse((response) => response.request().method() === 'PUT' && response.url().endsWith('/acquaintance/answers'));
      await next.click(); expect((await saved).status()).toBe(200);
      await expect(page.locator('#onboarding-title')).not.toHaveText(previousQuestion);
      await expect(next).toBeEnabled();
    };
    await expect(answer).toBeVisible();
    await next.click();
    await expect(page.locator('#onboarding-error')).toContainText('Напишите ответ');
    const text = ['Синтетические регулярные задачи и рабочие ситуации', 'Не знаю', 'Синтетические ограничения и взаимодействия'];
    await answer.fill(text[0]);
    await page.locator('#onboarding-home').click();
    await expect(page.locator('#onboarding-notice')).toContainText('Сейчас доступно продолжение знакомства');
    await expect(answer).toHaveValue(text[0]);
    await answer.fill(text[0]); // The persisted dirty draft remains editable after the management return.
    const geometry = [];
    for (const width of [1440, 1280, 768, 390, 360, 320]) {
      await page.setViewportSize({ width, height: 936 });
      await page.locator('.onboarding-copy').evaluate((element) => element.scrollIntoView({ block: 'start' }));
      const metrics = await page.locator('#onboarding-panel').evaluate((panel) => {
        const back = panel.querySelector('#onboarding-step-back').getBoundingClientRect();
        const input = panel.querySelector('textarea').getBoundingClientRect();
        const actions = panel.querySelector('.onboarding-actions').getBoundingClientRect();
        return { overflow: document.documentElement.scrollWidth > innerWidth + 1,
          font: getComputedStyle(panel).fontFamily, background: getComputedStyle(panel).backgroundColor,
          back: [back.width, back.height], gap: actions.top - input.bottom };
      });
      expect(metrics.overflow).toBe(false); expect(metrics.font).toContain('Onest');
      expect(metrics.background).toBe('rgb(246, 249, 249)'); expect(metrics.back).toEqual([44, 44]);
      expect(metrics.gap).toBeGreaterThanOrEqual(16); expect(metrics.gap).toBeLessThan(80);
      geometry.push({ width, ...metrics });
      await page.screenshot({ path: path.join(dir, `question-${width}.png`), fullPage: true });
    }
    await page.setViewportSize({ width: 640, height: 360 });
    await page.evaluate(() => { document.documentElement.style.zoom = '2'; });
    await next.scrollIntoViewIfNeeded(); await expect(next).toBeInViewport();
    await page.screenshot({ path: path.join(dir, 'question-short-zoom200.png'), fullPage: true });
    await page.evaluate(() => { document.documentElement.style.zoom = ''; });
    await page.setViewportSize({ width: 1440, height: 1000 });
    let interrupted = false;
    await page.route('**/acquaintance/answers', async (route) => {
      if (!interrupted) { interrupted = true; await route.abort('failed'); } else await route.continue();
    });
    await next.click();
    await expect(page.locator('#onboarding-error')).toBeVisible(); await expect(answer).toHaveValue(text[0]);
    await saveAnswer(text[0]);
    const secondQuestion = await page.locator('#onboarding-title').innerText();
    await page.reload(); await expect(page.locator('#onboarding-title')).toHaveText(secondQuestion);
    await expect(answer).toHaveValue('');
    await saveAnswer(text[1]);
    const thirdQuestion = await page.locator('#onboarding-title').innerText();
    await page.reload(); await expect(page.locator('#onboarding-title')).toHaveText(thirdQuestion);
    await saveAnswer(text[2]);
    await expect(page.locator('#onboarding-title')).toHaveText('Проверьте ваши ответы');
    await page.reload(); await expect(page.locator('#onboarding-title')).toHaveText('Проверьте ваши ответы');
    await expect(page.locator('.onboarding-summary-answer')).toHaveText(text);
    await page.locator('[data-edit-answer="1"]').click();
    text[1] = 'Синтетическая адресная правка второго ответа';
    await saveAnswer(text[1]);
    await expect(page.locator('.onboarding-summary-answer')).toHaveText(text);
    let lostPreparationReply = false;
    await page.route('**/users/assessment/cycles/prepare', async (route) => {
      const response = await route.fetch(); // The real server commits before the response is lost.
      expect(response.status()).toBe(202); lostPreparationReply = true; await route.abort('failed');
    });
    await next.dblclick();
    await expect(page.locator('#onboarding-title')).toHaveText('Что показывает оценка 4К');
    await expect.poll(async () => (await snapshot()).operations).toBe(1);
    expect((await snapshot()).started).toBe(0);
    await expect.poll(() => lostPreparationReply).toBe(true);
    await expect.poll(async () => (await savedAcquaintance()).onboarding.current_step).toBe(6);
    await page.reload(); await expect(page.locator('#onboarding-title')).toHaveText('Что показывает оценка 4К');
    await page.locator('#onboarding-skip').click();
    // Entering readiness re-reads the committed server operation, not another prepare POST.
    await expect(page.locator('#onboarding-title')).toHaveText('Готовим вашу оценку');
    const code = (await page.locator('#feature-list').innerText()).match(/[a-f0-9]{8}-[a-f0-9-]{27,}/)[0];
    await page.reload();
    await expect(page.locator('#onboarding-title')).toHaveText('Готовим вашу оценку');
    await expect(page.locator('#feature-list')).toContainText(code);
    const second = await participantContext.newPage(); await second.goto(base);
    await expect(second.locator('#onboarding-title')).toHaveText('Готовим вашу оценку');
    expect((await snapshot()).operations).toBe(1);
    preparationReceiptRequired = fullPath;
    await page.request.post(base + '/__pytest__/release-preparation');
    step = 'real_llm_preparation';
    await expect.poll(
      async () => page.locator('#onboarding-title').innerText(),
      { timeout: realProvider ? 600000 : 45000 },
    ).toMatch(/^(Можно приступать к оценке|Не удалось подготовить оценку)$/);
    const preparationReceipt = fullPath
      ? await (await page.request.get(base + '/__pytest__/path-receipt')).json()
      : null;
    if (fullPath) {
      save('source-to-runtime-receipt', preparationReceipt);
      terminalPreparationReceiptSaved = isTerminalPreparationReceipt(preparationReceipt);
      await test.info().attach('superadmin-to-preparation-receipt', {
        path: path.join(dir, 'source-to-runtime-receipt.json'), contentType: 'application/json',
      });
    }
    expect(await page.locator('#onboarding-title').innerText()).toBe('Можно приступать к оценке');
    if (fullPath) {
      if (state.path29.input_mode === 'published-pilot') verifyPublishedProgram(preparationReceipt, selectedRelease);
      verifyPreparation(preparationReceipt);
    }
    expect(await snapshot()).toEqual({ profiles: 1, cycles: 1, started: 0, operations: 1 });
    await page.reload(); await expect(page.locator('#onboarding-title')).toHaveText('Можно приступать к оценке');
    const freshContext = await browser.newContext(); extraContexts.push(freshContext);
    const fresh = await freshContext.newPage(); await fresh.goto(base);
    await fresh.locator('#email-input').fill(state.path29.participant_email);
    await fresh.locator('#request-magic-link-button').click();
    await fresh.locator('#magic-token-input').fill(state.password);
    await fresh.locator('#verify-magic-link-button').click();
    await expect(fresh.locator('#onboarding-panel')).toBeVisible();
    await expect(fresh.locator('#onboarding-title')).toHaveText('Можно приступать к оценке');
    await expect(fresh.locator('.onboarding-summary-answer')).toHaveText(text);
    expect(await snapshot()).toEqual({ profiles: 1, cycles: 1, started: 0, operations: 1 });
    await page.locator('#onboarding-home').click();
    await expect(page.locator('#dashboard-panel')).toBeVisible();
    let releaseAcquaintance;
    await page.route('**/users/*/acquaintance', (route) => { releaseAcquaintance = () => route.continue(); });
    await page.locator('#assessment-action-button').click();
    await expect(page.locator('#onboarding-panel')).toBeVisible();
    await expect(page.locator('#prechat-panel')).toBeHidden();
    await expect(page.locator('#onboarding-title')).toHaveText('Загружаем знакомство');
    await expect(next).toBeDisabled();
    await expect.poll(() => typeof releaseAcquaintance).toBe('function');
    await releaseAcquaintance(); await page.unroute('**/users/*/acquaintance');
    await expect(page.locator('#onboarding-title')).toHaveText('Можно приступать к оценке');
    expect(await snapshot()).toEqual({ profiles: 1, cycles: 1, started: 0, operations: 1 });
    await page.screenshot({ path: path.join(dir, 'ready.png'), fullPage: true });
    await capturePathViewports(page, dir, 'participant-ready', [
      { name: 'readiness-explanation', locator: page.locator('#onboarding-title') },
      { name: 'explicit-start', locator: next },
    ]);
    step = 'explicit_start_and_first_as';
    const startResponse = page.waitForResponse((response) => response.request().method() === 'POST'
      && response.url().endsWith('/users/assessment/cycles/start'));
    await next.dblclick();
    const started = await startResponse;
    expect(started.status()).toBe(201);
    await expect(page.locator('#interview-panel')).toBeVisible();
    await expect(page.locator('.interview-message--situation').first()).toBeVisible();
    expect(await snapshot()).toEqual({ profiles: 1, cycles: 1, started: 1, operations: 1 });
    await page.screenshot({ path: path.join(dir, 'first-case.png'), fullPage: true });
    await capturePathViewports(page, dir, 'first-as', [
      { name: 'home', locator: page.locator('#interview-profile-button') },
      { name: 'answer-input', locator: page.locator('#interview-textarea') },
      { name: 'pause', locator: page.locator('#interview-pause-button') },
      { name: 'finish', locator: page.locator('#interview-finish-button') },
      { name: 'answer-submit', locator: page.locator('#interview-submit-button') },
    ]);
    // Resizing/reading must not start another Cycle or create assessment answers.
    expect(await snapshot()).toEqual({ profiles: 1, cycles: 1, started: 1, operations: 1 });
    const repeatedAssignment = await admin.request.post(base +
      `/users/admin/organizations/${state.path29.organization_id}/assessment-assignments`, { data: {
        user_ids: [participantId], assignment_ref: state.path29.assignment_ref || 'PATH29 browser',
        operation_id: 'post-start-replay-' + runId,
      } });
    expect(repeatedAssignment.status()).toBe(200);
    const repeatedAssignmentResult = await repeatedAssignment.json();
    expect(repeatedAssignmentResult.items[0].status).toBe('already_assigned');
    expect(await snapshot()).toEqual({ profiles: 1, cycles: 1, started: 1, operations: 1 });
    save('post-start-assignment-replay', { status: repeatedAssignment.status(),
      result: repeatedAssignmentResult, participant_state: await snapshot(),
      scope: fullPath ? 'real-provider PATH' : 'SYNTHETIC component plan boundary; assignment/SQL real' });
    if (fullPath) {
      const receipt = await (await page.request.get(base + '/__pytest__/path-receipt')).json();
      const runtimeResponse = await page.request.get(base + '/users/assessment/cycles/' + receipt.cycle.cycle_id + '/runtime');
      expect(runtimeResponse.status()).toBe(200);
      const runtime = await runtimeResponse.json();
      verifyPreparation(receipt);
      expect(receipt.cycle.started_at).toBeTruthy();
      expect(receipt.sessions[0].started_at).toBeTruthy();
      expect(receipt.assessment_situation.started_at).toBeTruthy();
      expect(receipt.assessment_answers).toBe(0);
      expect(receipt.assessment_situation.assessment_situation_id)
        .toBe(preparationReceipt.assessment_situation.assessment_situation_id);
      expect(receipt.functional_generation.candidate_checksum)
        .toBe(preparationReceipt.functional_generation.candidate_checksum);
      expect(receipt.assessment_situation.snapshot_checksum)
        .toBe(preparationReceipt.assessment_situation.snapshot_checksum);
      expect(runtime.current_situation.assessment_situation_id)
        .toBe(receipt.assessment_situation.assessment_situation_id);
      expect(checksum(runtime.current_situation.participant_payload))
        .toBe(receipt.saved_checksums.participant_payload);
      const introduction = runtime.current_situation.participant_payload.introduction;
      expect(introduction).toBeTruthy();
      await expect(page.locator('.interview-message--situation').first()).toContainText(introduction);
      finalReceipt = { ...receipt, browser: browser.version(), http_start_status: started.status(),
        participant_state: await snapshot(), presented_as: {
          assessment_situation_id: runtime.current_situation.assessment_situation_id,
          participant_payload_checksum: checksum(runtime.current_situation.participant_payload),
          dom_introduction_matched: true, screenshot: 'first-case.png',
        } };
      save('first-case-receipt', finalReceipt);
      verifyFirstCase(finalReceipt, preparationReceipt, selectedRelease);
      expect(['functional-diagnostic', 'published-pilot']).toContain(state.path29.input_mode);
      expect(receipt.program_definition.id).toBe(state.path29.program_id);
      expect(receipt.program_definition.assessment_configuration_id).toBe(state.path29.configuration_id);
      expect(receipt.program_definition.catalog_version_id).toBe(receipt.catalog.id);
      expect(receipt.assessment_configuration.catalog_version_id).toBe(receipt.catalog.id);
      if (state.path29.input_mode === 'published-pilot') {
        expect(receipt.program_definition.code).toBe('specialist_pilot');
        verifyPublishedProgram(receipt, selectedRelease);
        expect(receipt.case_versions.map((item) => item.case_id)).toEqual(
          Array.from({ length: 9 }, (_, i) => 'CASE.SPEC.' + String(i + 1).padStart(2, '0')));
      } else {
        expect(receipt.case_versions).toHaveLength(1);
        expect(receipt.case_versions[0].case_id).toBe('CASE.SPEC.02');
      }
      expect(receipt.functional_generation.present).toBe(true);
      expect(receipt.functional_generation.admitted_for_participant).toBe(true);
      expect(receipt.functional_generation.candidate_checksum).toMatch(/^[a-f0-9]{64}$/);
      await test.info().attach('superadmin-to-first-case-readback', {
        body: JSON.stringify({ browser: browser.version(), organization_id: state.path29.organization_id,
          program_id: state.path29.program_id, participant_state: await snapshot(), assessment_answers: 0,
          source_to_runtime_receipt: finalReceipt }),
        contentType: 'application/json',
      });
      await test.info().attach('superadmin-to-first-case-first-case', {
        path: path.join(dir, 'first-case.png'), contentType: 'image/png',
      });
      if (compositeProfile) {
        step = 'complete_started_assessment_to_report';
        executionStarted = true;
        executionCycleId = receipt.cycle.cycle_id;
        const firstCaseReceipt = finalReceipt;
        const contourReceipt = await completeStartedAssessment({
          page, base, cycleId: receipt.cycle.cycle_id, runId,
          evidenceDir: dir,
          initialSituationId: receipt.assessment_situation.assessment_situation_id,
        });
        contourReceipt.first_case_receipt = {
          file: 'first-case-receipt.json',
          sha256: createHash('sha256').update(fs.readFileSync(path.join(dir, 'first-case-receipt.json'))).digest('hex'),
          assessment_answers: firstCaseReceipt.assessment_answers,
        };
        save('execution-contour-receipt', contourReceipt);
        finalReceipt = contourReceipt;
        terminalReceiptFile = 'execution-contour-receipt.json';
        await test.info().attach('execution-contour-receipt', {
          path: path.join(dir, terminalReceiptFile), contentType: 'application/json',
        });
      }
      scenarioCompleted = true;
      return;
    }
    const ownAnswer = 'Синтетический первый ответ: уточню условия и согласую следующий шаг.';
    await page.locator('#interview-textarea').fill(ownAnswer);
    const sent = page.waitForResponse((response) => response.request().method() === 'POST' && response.url().endsWith('/turns'));
    await page.locator('#interview-submit-button').click();
    expect((await sent).status()).toBe(200);
    await expect(page.locator('#interview-messages .own')).toContainText([ownAnswer]);
    await page.locator('#interview-profile-button').click();
    await expect(page.locator('#dashboard-panel')).toBeVisible();
    await page.locator('.user-chip[aria-label="Меню пользователя"]').focus();
    await page.locator('#dashboard-onboarding-button').click();
    await expect(page.locator('#onboarding-panel')).toBeVisible();
    await expect(page.locator('#onboarding-title')).toHaveText('Что показывает оценка 4К');
    await expect(page.locator('#onboarding-panel')).not.toContainText('Подготовленный план пока недоступен');
    await next.click();
    await expect(page.locator('#interview-panel')).toBeVisible();
    const afterReview = await snapshot();
    expect(afterReview.profiles).toBe(1); expect(afterReview.cycles).toBe(1); expect(afterReview.started).toBe(1);
    await test.info().attach('path29-browser-and-geometry', { body: JSON.stringify({ browser: browser.version(), geometry }), contentType: 'application/json' });
    for (const name of ['question-1440', 'question-1280', 'question-768', 'question-390', 'question-360',
      'question-320', 'question-short-zoom200', 'ready', 'first-case']) {
      await test.info().attach(`path29-${name}`, { path: path.join(dir, `${name}.png`), contentType: 'image/png' });
    }
    console.log('PATH29 owned screenshots and server log:', dir);
  } catch (error) {
    let failureReceipt;
    try {
      if (server && server.exitCode === null) {
        failureReceipt = await (await page.request.get(base + '/__pytest__/path-receipt')).json();
        save('failure-receipt', failureReceipt);
        terminalPreparationReceiptSaved ||= isTerminalPreparationReceipt(failureReceipt);
      }
    } catch { /* Startup failures may have no HTTP endpoint. */ }
    try {
      await captureFailurePage(activePage, dir, { step, actor: activeActor });
    } catch { /* Closed or unavailable active tabs must not discard server evidence. */ }
    const preparationError = failureReceipt?.preparation_operation?.error_message;
    save('failure', { step,
      expected: step === 'real_llm_preparation' ? 'Admission конечного кандидата и сохранённая AS' : 'Согласованный шаг завершён штатно',
      actual: preparationError || error.message.replace(/\u001b\[[0-9;]*m/g, ''),
      classification: preparationError ? 'product_preparation_blocker' : 'diagnostic_assertion_or_environment_failure' });
    throw error;
  } finally {
    let terminalExecutionExportSaved = false;
    if (executionStarted) {
      try {
        if (!server || server.exitCode !== null) throw new Error('EXECUTION_SERVER_UNAVAILABLE');
        const exported = await readExecutionExport(page, base, executionCycleId, runId, dir);
        if (!terminalExecutionKnown(exported.value)) throw new Error('EXECUTION_OUTCOME_UNKNOWN');
        terminalExecutionExportSaved = true;
      } catch (exportError) {
        try {
          save('cleanup-deferred', { run_id: runId, reason: 'TERMINAL_EXECUTION_EXPORT_UNVERIFIED',
            detail: exportError.message, database_preserved: true });
        } catch { /* Preserve the DB even when diagnostic storage is unavailable. */ }
      }
    }
    try {
      if (server && server.exitCode === null) {
        const exited = new Promise((resolve) => server.once('exit', resolve)); server.kill('SIGTERM');
        await Promise.race([exited, new Promise((resolve) => setTimeout(resolve, 5000))]);
        if (server.exitCode === null) { server.kill('SIGKILL'); await exited; }
      }
    } finally {
      try {
        if (executionStarted && !terminalExecutionExportSaved) {
          throw new Error('Cleanup deferred: terminal execution export or readback unavailable');
        }
        if (preparationReceiptRequired && !terminalPreparationReceiptSaved) {
          save('cleanup-deferred', { reason: 'TERMINAL_PREPARATION_RECEIPT_NOT_PERSISTED',
            state_path: statePath, database_preserved: true });
          throw new Error('Cleanup deferred: preserve owned DB until diagnostic receipt is saved');
        }
        try { cli('destroy'); }
        catch (cleanupError) {
          save('cleanup-error', { run_id: runId, reason: 'OWNED_DESTROY_FAILED',
            detail: cleanupError.message });
          throw cleanupError;
        }
      }
      finally { await Promise.allSettled([superContext.close(), adminContext.close(), participantContext.close(), ...extraContexts.map((context) => context.close())]); }
      if (fullPath) save('completion', { run_id: runId, status: scenarioCompleted ? 'completed' : 'failed',
        exit_code: scenarioCompleted ? 0 : 1, receipt_file: terminalReceiptFile,
        receipt_sha256: scenarioCompleted
          ? createHash('sha256').update(fs.readFileSync(path.join(dir, terminalReceiptFile))).digest('hex') : null });
    }
  }
});
