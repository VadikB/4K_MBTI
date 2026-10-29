import { test, expect } from '@playwright/test';
import { spawn, spawnSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { randomUUID } from 'node:crypto';

test('PATH29 owned backend: invitation → scoped chat → durable preparation → explicit first case', async ({ browser }) => {
  test.setTimeout(240000);
  if (!process.env.STAND_ADMIN_URL) throw new Error('Explicit isolated STAND_ADMIN_URL required');
  const root = process.cwd(), python = process.env.BROWSER_PYTHON || path.join(root, '.venv/bin/python');
  const dir = path.join(root, '.test-stand/path29', randomUUID());
  fs.mkdirSync(dir, { recursive: true });
  const statePath = path.join(dir, 'state.json'), base = 'http://127.0.0.1:18859';
  const run = (script, args) => {
    const result = spawnSync(python, [script, ...args], { encoding: 'utf8', timeout: 180000 });
    if (result.status !== 0) throw new Error(script + ': ' + result.stderr + result.stdout);
  };
  const cli = (action) => run('scripts/test_stand.py', [action, '--state', statePath, '--port', '18859', '--gateway', '1']);
  const adminContext = await browser.newContext(), participantContext = await browser.newContext();
  const extraContexts = [];
  const admin = await adminContext.newPage(), page = await participantContext.newPage();
  let server;
  cli('create');
  try {
    cli('bootstrap');
    run('tests/path29_browser_inputs.py', ['--state', statePath]);
    const state = JSON.parse(fs.readFileSync(statePath, 'utf8'));
    const fd = fs.openSync(path.join(dir, 'server.log'), 'a');
    server = spawn(python, ['tests/path29_browser_server.py', '--state', statePath], { stdio: ['ignore', fd, fd] });
    fs.closeSync(fd);
    await expect.poll(async () => { try { return (await fetch(base + '/health/ready')).status; } catch { return 0; } }, { timeout: 30000 }).toBe(200);
    const snapshot = async () => (await page.request.get(base + '/__pytest__/participant-state')).json();
    expect(await snapshot()).toEqual({ profiles: 0, cycles: 0, started: 0, operations: 0 });
    await admin.goto(base);
    await admin.locator('#email-input').fill(state.path29.admin_email);
    await admin.locator('#request-magic-link-button').click();
    await admin.locator('#magic-token-input').fill(state.password);
    await admin.locator('#verify-magic-link-button').click();
    await expect(admin.locator('#admin-organizations-panel')).toBeVisible();
    const card = admin.locator(`[data-organization-id="${state.path29.organization_id}"]`);
    await card.getByRole('button', { name: 'Данные организации', exact: true }).click();
    const form = card.locator('[data-action="preview-early-data"]');
    const values = { assignment_ref: 'PATH29 browser', source_author: 'Синтетический заказчик',
      organization_name: 'Синтетическая организация PATH29', organization_type: 'Компания', industry: 'ИТ',
      activity_description: 'Синтетическая проверка пути участника', purpose: 'Синтетическая цель развития',
      results_usage: 'Для синтетического плана развития', result_recipients: 'Участник', organizer: 'Синтетический HR',
      responsible_contact: state.path29.admin_email, case_reality_level: 'Реальные', organization_name_usage_rules: 'Разрешено' };
    for (const [name, value] of Object.entries(values)) await form.locator(`[name="${name}"]`).fill(value);
    await form.getByRole('button', { name: 'Сохранить черновик и предпросмотр' }).click();
    await card.locator('.admin-questionnaire-preview').getByRole('button', { name: 'Подтвердить сведения' }).click();
    await expect(card.locator('.admin-questionnaire-confirmation')).toContainText('Сведения подтверждены');
    await card.getByRole('button', { name: 'Организация и участники', exact: true }).click();
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
    await card.getByRole('button', { name: 'Назначить оценку', exact: true }).click();
    const sources = card.locator('[data-assignment-sources]');
    await expect(sources).toBeVisible();
    await expect(card.locator('[data-operation-status]').first()).toContainText('Источники пока не назначены');
    await expect(sources.locator('[name="assessment_configuration_id"]')).toHaveValue('');
    await sources.locator('[name="assessment_configuration_id"]').selectOption(String(state.path29.configuration_id));
    await sources.locator('[name="role_profile_version_id"]').selectOption(String(state.path29.role_version_id));
    await checkbox.check();
    await card.getByRole('button', { name: 'Назначить оценку', exact: true }).click();
    await expect(card.locator('[data-operation-status]').first()).toContainText('Опубликованные источники назначены');
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
    await page.goto(base + '/' + invitation.search);
    await expect(page.locator('#magic-token-input')).toBeVisible();
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
    await expect(page.locator('#onboarding-notice')).toContainText('неотправленный текст');
    await expect(answer).toHaveValue(text[0]);
    await answer.fill(text[0]); // Editing clears stale validation/navigation messages.
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
    await page.request.post(base + '/__pytest__/release-preparation');
    await expect(page.locator('#onboarding-title')).toHaveText('Можно приступать к оценке', { timeout: 45000 });
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
    await next.dblclick();
    await expect(page.locator('#interview-panel')).toBeVisible();
    await expect(page.locator('.interview-message--situation').first()).toBeVisible();
    expect(await snapshot()).toEqual({ profiles: 1, cycles: 1, started: 1, operations: 1 });
    await page.screenshot({ path: path.join(dir, 'first-case.png'), fullPage: true });
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
  } finally {
    try {
      if (server && server.exitCode === null) {
        const exited = new Promise((resolve) => server.once('exit', resolve)); server.kill('SIGTERM');
        await Promise.race([exited, new Promise((resolve) => setTimeout(resolve, 5000))]);
        if (server.exitCode === null) { server.kill('SIGKILL'); await exited; }
      }
    } finally {
      try { cli('destroy'); }
      finally { await Promise.allSettled([adminContext.close(), participantContext.close(), ...extraContexts.map((context) => context.close())]); }
    }
  }
});
