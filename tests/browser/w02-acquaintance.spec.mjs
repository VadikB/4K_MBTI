import { test, expect } from '@playwright/test';
import fs from 'node:fs/promises';
import http from 'node:http';
import path from 'node:path';

let server, base;
const evidence = process.env.W02_EVIDENCE_DIR;
const schema = JSON.parse(await fs.readFile('assessment_definitions/questionnaires/participant_context/corporate/1.0/definition.json'));
const json = (route, body, status = 200) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) });
test.beforeAll(async () => {
  server = http.createServer(async (request, response) => {
    try {
      const pathname = new URL(request.url, 'http://127.0.0.1').pathname;
      const file = path.join(process.cwd(), pathname === '/' ? 'web/index.html' : pathname);
      response.setHeader('Content-Type', ({ '.css': 'text/css', '.html': 'text/html', '.js': 'application/javascript', '.woff': 'font/woff', '.svg': 'image/svg+xml' })[path.extname(file)] || 'application/octet-stream');
      response.end(await fs.readFile(file));
    } catch { response.statusCode = 404; response.end('missing'); }
  });
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  base = `http://127.0.0.1:${server.address().port}`;
  if (process.env.W02_RESOURCE_LOG) await fs.appendFile(process.env.W02_RESOURCE_LOG, JSON.stringify({ event: 'start', owner: 'P4K-W02-01', pid: process.pid, port: server.address().port, db: null }) + '\n');
});
test.afterAll(async () => {
  if (!server?.listening) return;
  const port = server.address().port;
  await new Promise((resolve) => server.close(resolve));
  if (process.env.W02_RESOURCE_LOG) await fs.appendFile(process.env.W02_RESOURCE_LOG, JSON.stringify({ event: 'stop', pid: process.pid, port, listening: server.listening }) + '\n');
});
async function fixture(page) {
  const user = { id: 8, email: 'synthetic@example.test', full_name: 'Синтетический Участник' };
  const model = {
    readiness: { status: 'ready', organization_id: 10, organization_name: 'Синтетическая организация', assignment_ref: 'w02-owned', questionnaire_revision_id: 41,
      briefing: { organizer: 'Синтетическая организация', purpose: 'Цель из назначенного briefing', results_usage: 'Использование из назначенного briefing',
        result_recipients: 'Свой готовый отчёт видит участник. Готовые отчёты организации видят её действующие администраторы.',
        question_schema: { variant: schema.variant, version: schema.version, questions: schema.questions }, questions: schema.questions.map((q) => q.text),
        provided_participant_fields: [{ key: 'full_name', label: 'ФИО', value: user.full_name }, { key: 'position', label: 'Должность', value: null }, { key: 'role', label: 'Роль в оценке', value: 'Специалист из назначения' }],
        consent_text: 'Действующий серверный текст согласия, версия 7.', consent_version: 7 } },
    assignment_id: 91, state: { answers_json: {} }, mandatory_complete: false,
    onboarding: { status: 'not_started', current_step: 0 }, late_readiness: { status: 'waiting_for_assessment_data' },
    competency_explanation: { status: 'ready', items: ['Коммуникация', 'Командная работа', 'Креативность', 'Критическое мышление'].map((name) => ({ name, definition: 'Синтетическое назначенное определение' })) },
  };
  const writes = [], unexpected = [];
  let failSave = false, failIssue = false;
  await page.route('**/users/**', async (route) => {
    const req = route.request(), pathname = new URL(req.url()).pathname;
    if (req.method() !== 'GET') writes.push({ path: pathname, body: req.postDataJSON() });
    if (pathname === '/users/session/restore') return json(route, { authenticated: true, user, is_admin: false, dashboard: {} });
    if (pathname === '/users/8/session-bootstrap') return json(route, { user, is_admin: false, dashboard: {} });
    if (pathname === '/users/8/journey-state') return json(route, { next_action: 'show_onboarding', can_open_dashboard: true,
      profile: { status: 'complete' }, onboarding: model.onboarding, assessment: { status: 'not_started' }, acquaintance: model });
    if (pathname === '/users/8/acquaintance' || pathname === '/users/8/acquaintance/resolve-profile') return json(route, model);
    if (pathname === '/users/8/onboarding') { model.onboarding = req.postDataJSON(); return json(route, model.onboarding); }
    if (pathname === '/users/8/acquaintance/consent') {
      expect(req.postDataJSON()).toEqual({ version: 7 });
      model.state.consent_accepted_at = 'synthetic'; model.state.consent_version = 7; return json(route, model.state);
    }
    if (pathname === '/users/8/acquaintance/answers') {
      if (failSave) { failSave = false; return json(route, { detail: 'controlled save failure' }, 503); }
      const body = req.postDataJSON();
      Object.assign(model.state.answers_json, body.answers);
      if (body.confirm) { model.mandatory_complete = true; model.state.answers_confirmed_at = 'synthetic'; }
      return json(route, model.state);
    }
    if (pathname === '/users/8/acquaintance/issues') {
      if (failIssue) { failIssue = false; return route.abort('failed'); }
      return json(route, { id: 42, status: 'new', created_at: '2026-11-14T12:00:00Z' }, 201);
    }
    if (pathname === '/users/version') return json(route, { version: 'w02-controlled' });
    unexpected.push(`${req.method()} ${pathname}`); return json(route, {}, 404);
  });
  return { model, writes, unexpected, failSave: () => { failSave = true; }, failIssue: () => { failIssue = true; } };
}
const next = (page) => page.locator('#onboarding-next');
const dialog = (page) => page.locator('#onboarding-dialog');
async function checkIssue(page, run, fail = false) {
  const before = JSON.stringify(run.model);
  await page.getByRole('button', { name: 'Сообщить о неточности', exact: true }).click();
  await dialog(page).getByLabel('Что нужно проверить?').fill('Синтетическая неточность сведений');
  if (fail) run.failIssue();
  await dialog(page).getByRole('button', { name: 'Отправить', exact: true }).click();
  if (fail) {
    await expect(dialog(page).getByRole('alert')).toBeVisible();
    await expect(dialog(page).getByLabel('Что нужно проверить?')).toHaveValue('Синтетическая неточность сведений');
    await expect(dialog(page).getByRole('status')).toBeHidden();
    await dialog(page).getByRole('button', { name: 'Отправить', exact: true }).click();
  }
  await expect(dialog(page).getByRole('status')).toContainText('Сообщение сохранено в вашей организации');
  await dialog(page).getByRole('button', { name: 'Продолжить знакомство', exact: true }).click();
  await expect(page.locator('#onboarding-report-issue')).toBeFocused();
  expect(JSON.stringify(run.model)).toBe(before);
}
for (const width of [1440, 390, 320]) {
  test(`W02 path, shared edit, failures, issue receipts and history at ${width}px`, async ({ page }, info) => {
    test.setTimeout(90000);
    await page.setViewportSize({ width, height: width === 1440 ? 1024 : 844 });
    const run = await fixture(page);
    const errors = []; page.on('pageerror', (error) => errors.push(error.message));
    await page.goto(base);
    await expect(page.locator('#onboarding-title')).toHaveText('Рады знакомству!');
    await expect(page.locator('#onboarding-panel')).toContainText('Цель из назначенного briefing');
    await expect(page.locator('.onboarding-answer')).toBeDisabled();
    expect(await page.locator('.onboarding-send-placeholder').evaluate((node) => getComputedStyle(node).opacity)).toBe('1');
    await expect(page.locator('#onboarding-panel .step-progress')).toHaveCount(0);
    await expect(page.locator('#onboarding-panel')).not.toContainText('алгоритмами AI');
    await page.screenshot({ path: info.outputPath(`welcome-${width}.png`) });
    await next(page).click();
    await expect(page.locator('#onboarding-panel')).toContainText('Действующий серверный текст согласия, версия 7.');
    await expect(page.locator('#onboarding-panel')).toContainText('Специалист из назначения');
    await expect(page.locator('#onboarding-panel')).toContainText('Не указано');
    await checkIssue(page, run, width === 1440);
    await next(page).click();
    const original = ['Синтетические рабочие задачи.', 'Синтетические решения.', 'Ограничение и взаимодействие.'];
    for (let index = 0; index < 3; index++) {
      await expect(page.locator('#onboarding-title')).toHaveText(schema.questions[index].text);
      await expect(page.locator('#onboarding-question-number')).toHaveText(`ВОПРОС ${index + 1} ИЗ 3`);
      if (index === 0) await page.screenshot({ path: info.outputPath(`question-${width}.png`) });
      await page.locator('.onboarding-answer').fill(original[index]);
      await next(page).click();
    }
    await expect(page.locator('#onboarding-title')).toHaveText('Всё верно?');
    await expect(page.locator('#feature-list .onboarding-summary-answer')).toHaveText(original);
    await next(page).focus(); await page.keyboard.press('Tab');
    await expect(page.locator('#onboarding-edit-answers')).toBeFocused();
    expect(await page.locator('#onboarding-edit-answers').evaluate((node) => getComputedStyle(node).outlineColor)).toBe('rgb(0, 125, 137)');
    await page.screenshot({ path: info.outputPath(`summary-${width}.png`) });
    await checkIssue(page, run);
    await page.getByRole('button', { name: 'Изменить мои ответы', exact: true }).click();
    await expect(dialog(page).locator('textarea')).toHaveCount(3);
    await page.locator('#onboarding-edit-1').fill('Отменяемый ответ');
    await dialog(page).getByRole('button', { name: 'Отмена', exact: true }).click();
    await expect(page.locator('#onboarding-edit-answers')).toBeFocused();
    await expect(page.locator('#feature-list .onboarding-summary-answer')).toHaveText(original);
    await page.getByRole('button', { name: 'Изменить мои ответы', exact: true }).click();
    const edited = width === 320 ? 'ДлинныйОтвет'.repeat(250) : 'Уточнённые решения из общей формы';
    await page.locator('#onboarding-edit-1').fill(edited);
    run.failSave();
    await dialog(page).getByRole('button', { name: 'Сохранить', exact: true }).click();
    await expect(dialog(page).getByRole('alert')).toBeVisible();
    await expect(page.locator('#onboarding-edit-1')).toHaveValue(edited);
    expect(run.model.mandatory_complete).toBe(false);
    await expect(page.locator('#feature-list .onboarding-summary-answer')).toHaveText(original);
    await page.screenshot({ path: info.outputPath(`edit-error-${width}.png`) });
    await dialog(page).getByRole('button', { name: 'Сохранить', exact: true }).click();
    await expect(dialog(page)).not.toBeVisible();
    original[1] = edited;
    await expect(page.locator('#feature-list .onboarding-summary-answer')).toHaveText(original);
    await page.reload();
    await expect(page.locator('#feature-list .onboarding-summary-answer')).toHaveText(original);
    await next(page).click();
    await expect(page.locator('#onboarding-title')).toHaveText('Что такое 4К');
    await expect(page.locator('#feature-list')).toContainText('Один ответ не определяет общую картину');
    await page.reload();
    await expect(page.locator('#onboarding-title')).toHaveText('Что такое 4К');
    // Return through the product dashboard and its existing read-only history entry.
    await page.locator('#onboarding-home').click();
    await expect(page.locator('#dashboard-panel')).toBeVisible();
    await page.locator('#dashboard-panel .user-chip').click();
    await page.locator('#dashboard-onboarding-button').click();
    await expect(page.locator('#onboarding-title')).toHaveText('Знакомство завершено');
    await expect(page.locator('.onboarding-answer')).toBeDisabled();
    await expect(page.locator('#onboarding-home')).toBeEnabled();
    await expect(page.getByRole('button', { name: 'Изменить мои ответы', exact: true })).toHaveCount(0);
    await expect(page.locator('#onboarding-messages')).toContainText(edited);
    const geometry = await page.evaluate(() => {
      const panel = document.getElementById('onboarding-panel');
      const style = (selector) => getComputedStyle(panel.querySelector(selector));
      const label = panel.querySelector('.onboarding-section-label').getBoundingClientRect();
      return { bodyWidth: document.documentElement.scrollWidth, panel: getComputedStyle(panel).backgroundColor,
        assistant: style('.onboarding-bubble').backgroundColor, user: style('.onboarding-message--user .onboarding-bubble').backgroundColor,
        focus: style('#onboarding-next').outlineColor, buttonHeight: panel.querySelector('#onboarding-next').getBoundingClientRect().height,
        composer: panel.querySelector('.onboarding-composer').getBoundingClientRect().bottom,
        labelCenter: (label.left + label.right) / 2, labelRight: label.right, font: style('.onboarding-bubble').fontFamily };
    });
    expect(geometry.bodyWidth).toBeLessThanOrEqual(width);
    expect(geometry.panel).toBe('rgb(247, 247, 247)');
    expect(geometry.assistant).toBe('rgb(255, 255, 255)');
    expect(geometry.user).toBe('rgb(179, 235, 239)');
    expect(geometry.font).toContain('Onest');
    expect(geometry.composer).toBeLessThanOrEqual(width === 1440 ? 1024 : 844);
    expect(geometry.buttonHeight).toBeGreaterThanOrEqual(48);
    if (width === 1440) expect(geometry.labelCenter).toBeCloseTo(width / 2, 0);
    else expect(geometry.labelRight).toBeCloseTo(width - 16, 0);
    await fs.writeFile(info.outputPath('computed-styles.json'), JSON.stringify(geometry, null, 2));
    await page.screenshot({ path: info.outputPath(`history-${width}.png`) });
    expect(errors).toEqual([]); expect(run.unexpected).toEqual([]);
    expect(run.writes.filter((w) => /prepare|\/start$/.test(w.path))).toEqual([]);
    expect(run.writes.filter((w) => w.body?.confirm === true)).toHaveLength(1);
    await next(page).click();
    await expect(page.locator('#onboarding-title')).toHaveText('Для оценки ещё нужны сведения организации');
    expect(run.writes.filter((w) => /prepare|\/start$/.test(w.path))).toEqual([]);
    if (evidence) {
      await fs.mkdir(evidence, { recursive: true });
      const selected = new Set(['computed-styles.json', ...(width === 1440 ? ['welcome-1440.png', 'summary-1440.png'] :
        width === 390 ? ['question-390.png', 'history-390.png'] : ['edit-error-320.png', 'history-320.png'])]);
      for (const file of await fs.readdir(info.outputDir)) if (selected.has(file)) {
        await fs.copyFile(path.join(info.outputDir, file), path.join(evidence, `${width}-${file}`));
      }
    }
  });
}
