// One isolated fixture, production frontend and substituted HTTP only; no DB/LLM/mail.
import { test, expect } from '@playwright/test';
import fs from 'node:fs/promises';
import http from 'node:http';
import path from 'node:path';
let server, base;
const evidence = process.env.POSTW02_EVIDENCE;
const before = process.env.POSTW02_BEFORE === '1';
const progress = async (key) => {
  if (process.env.POSTW02_PROGRESS) await fs.writeFile(process.env.POSTW02_PROGRESS, JSON.stringify({ progress_key: key }));
};
test.beforeAll(async () => {
  server = http.createServer(async (req, res) => {
    try {
      const pathname = new URL(req.url, 'http://localhost').pathname;
      const file = path.join(process.cwd(), pathname === '/' ? 'web/index.html' : pathname);
      res.setHeader('Content-Type', { '.html': 'text/html', '.js': 'application/javascript', '.css': 'text/css', '.svg': 'image/svg+xml', '.woff': 'font/woff' }[path.extname(file)] || 'application/octet-stream');
      res.end(await fs.readFile(file));
    } catch { res.statusCode = 404; res.end('missing'); }
  });
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  base = `http://127.0.0.1:${server.address().port}`;
  if (evidence) { await fs.mkdir(evidence, { recursive: true }); await fs.writeFile(path.join(evidence, 'server.json'), JSON.stringify({ pid: process.pid, port: server.address().port, db: null, llm: 0, mail: 0 })); }
  await progress('server-start');
});
test.afterAll(async () => {
  if (!server?.listening) return;
  const port = server.address().port;
  await new Promise((resolve) => server.close(resolve));
  if (evidence) await fs.writeFile(path.join(evidence, 'cleanup.json'), JSON.stringify({ port, listening: server.listening }));
});
async function fixture(page) {
  const user = { id: 8, email: 'synthetic@example.test', full_name: 'Участник' };
  const card = { cycle_id: 'cabinet-cycle', title: 'Оценка универсальных компетенций специалистов по сопровождению сложных межфункциональных проектов и работе с клиентами',
    organization_name: 'Синтетическая организация с длинным названием', status: 'active', journey_state: 'active',
    status_label: 'Оценка начата', description: 'Продолжите с того же места.', action: 'continue', button_label: 'Продолжить',
    completed_cases: 6, completed_positions: 2, rules: { participant_notice: 'Правила сохранённого назначения.' }, total_cases: 8, planned_total: 8, current_position_no: 3, plan_revision_id: 'saved-plan', calendar_deadline: '2026-11-19T12:00:00Z' };
  const dashboard = {
    administrator_contact: { organization_name: card.organization_name, name: 'Администратор помощи', email: 'help@example.test' },
    current_assessments: [card], completed_assessments: [{ ...card, cycle_id: 'previous-cycle', current_position_no: null,
    title: 'Предыдущее прохождение', status: 'report_ready', journey_state: 'report_ready', status_label: 'Результат готов',
    description: 'Результат доступен.', action: 'open_report', button_label: 'Посмотреть результат', report_id: 'saved-report', calendar_deadline: null, closed_at: '2026-11-10T12:00:00Z' }] };
  const model = { assignment_id: 91, assessment_name: card.title, readiness: { status: 'ready',
    organization_id: 10, assignment_id: 91, assignment_ref: 'technical-assignment-key', questionnaire_revision_id: 41,
    briefing: { questions: ['Q1', 'Q2', 'Q3'], consent_version: 1 } }, mandatory_complete: true,
    state: { consent_version: 1, consent_accepted_at: 'synthetic', answers_json: { answer_1: 'A', answer_2: 'B', answer_3: 'C' } },
    onboarding: { status: 'completed', current_step: 8 }, late_readiness: { status: 'ready_to_prepare', personalized_profile_id: 4 },
    prepared_plan: { cycle_id: card.cycle_id, revision_id: card.plan_revision_id, start_readiness: { contract: 'm7_start_readiness/1', cycle_id: card.cycle_id, plan_revision_id: card.plan_revision_id, can_start: true, reasons: [] },
      plan: { route: Array.from({ length: 8 }, () => ({})), time_budget_seconds: 7200, calendar_window_seconds: 259200, participant_notice: 'Сохранённый методологический notice.' } } };
  const calls = [], unexpected = [];
  const journey = { next_action: 'show_dashboard', readFailure: false };
  const respond = (route, body) => route.fulfill({ contentType: 'application/json', body: JSON.stringify(body) });
  await page.route('**/users/**', (route) => {
    const request = route.request(), pathname = new URL(request.url()).pathname;
    calls.push({ method: request.method(), pathname });
    if (pathname === '/users/version') return respond(route, { version: 'synthetic' });
    if (pathname === '/users/session/restore') return respond(route, { authenticated: true, user, dashboard });
    if (pathname === '/users/8/session-bootstrap') return journey.readFailure
      ? route.fulfill({ status: 503, contentType: 'application/json', body: '{}' }) : respond(route, { user, dashboard });
    if (pathname === '/users/8/acquaintance/issues' && request.method() === 'GET') return respond(route, { items: [
      { organization_id: 10, assignment_id: 91, assignment_ref: model.readiness.assignment_ref, questionnaire_revision_id: 41,
        assessment_display_name: card.title,
        message: 'Исходное сообщение\n' + 'ОченьДлинноеОбращение'.repeat(60),
        reply_message: 'Ответ из сохранённого обращения.\n' + 'ДлинныйОтвет'.repeat(60),
        reply_author_display_name: 'Автор ответа', replied_at: '2026-11-19T12:00:00Z' },
      { organization_id: 10, assignment_id: 90, assignment_ref: model.readiness.assignment_ref, questionnaire_revision_id: 41,
        assessment_display_name: 'Оценка прежнего назначения',
        reply_message: 'Исторический ответ по прежнему назначению.', replied_at: '2026-11-19T10:00:00' },
      { assignment_ref: model.readiness.assignment_ref, message: 'Сообщение из старой записи',
        reply_message: 'Исторический ответ без подтверждённого назначения.', replied_at: '2026-11-19T09:00:00Z' },
    ] });
    if (pathname === '/users/8/journey-state') return respond(route, { next_action: journey.next_action, can_open_dashboard: true,
      profile: { status: 'complete' }, onboarding: model.onboarding, assessment: { status: 'in_progress', runtime_kind: 'cycle', cycle_id: card.cycle_id } });
    if (pathname === '/users/8/acquaintance') return respond(route, model);
    if (pathname === '/users/assessment/m7/cycles/cabinet-cycle/return-state') return respond(route, {
      cycle_id: 'cabinet-cycle', position_no: 3, current_assessment_situation_id: 'same-saved-as', current_assessment_situation_status: 'active',
      allowed_action: 'continue_current', recognized_absence_seconds: 180, remaining_seconds: 1200,
      calendar_deadline: '2026-11-19T12:00:00Z', progress: { completed_positions: 2, total_positions: 8 },
      planned_positions: 8, planned_total: true,
    });
    unexpected.push(`${request.method()} ${pathname}`);
    return route.fulfill({ status: 500, body: 'Unexpected fixture request' });
  });
  return { dashboard, card, model, calls, unexpected, journey };
}
for (const width of [1440, 390, 320]) {
  test(`POSTW02 cabinet at ${width}px`, async ({ page }) => {
    test.setTimeout(60000);
    await progress(`width-${width}`);
    await page.setViewportSize({ width, height: width === 1440 ? 1000 : 844 });
    const run = await fixture(page);
    const errors = []; page.on('pageerror', (e) => errors.push(e.message));
    await page.goto(base);
    await expect(page.locator('#dashboard-panel')).toBeVisible();
    await page.evaluate(() => document.fonts.ready);
    if (evidence && width !== 320) await page.screenshot({ path: path.join(evidence, `${before ? 'before' : 'after'}-${width}.png`), fullPage: true });
    if (!before) {
      await expect(page.locator('#current-assessments')).toContainText('3 ситуация из 8');
      await expect(page.getByRole('progressbar', { name: 'Завершено ситуаций' })).toHaveJSProperty('value', 2);
      await expect(page.locator('#current-assessments')).toContainText('2 из 8');
      await expect(page.locator('#current-assessments')).toContainText('19 ноября 2026, 15:00 МСК');
      await page.getByRole('button', { name: 'Условия прохождения' }).click();
      await expect(page.getByRole('dialog')).toContainText('Правила сохранённого назначения.');
      await page.keyboard.press('Escape');
      await expect(page.getByRole('button', { name: 'Условия прохождения' })).toBeFocused();
      const help = page.getByRole('button', { name: 'Связаться с администратором' });
      await help.click();
      await expect(page.getByRole('dialog').getByRole('link', { name: 'help@example.test' })).toHaveAttribute('href', 'mailto:help@example.test');
      await page.getByRole('dialog').getByRole('button', { name: 'Закрыть' }).click();
      await expect(help).toBeFocused();
      await expect(page.locator('.participant-appeal').nth(0)).toContainText('Автор ответа');
      await expect(page.locator('.participant-appeal').nth(0)).not.toContainText('Администратор помощи');
      await expect(page.locator('.participant-appeal').nth(1)).toContainText('Администратор ·');
      const replies = page.locator('.participant-appeal');
      await expect(replies.nth(0).locator('time')).toHaveAttribute('datetime', '2026-11-19T12:00:00Z');
      await expect(replies.nth(0).locator('time')).toHaveText('19.11.2026, 15:00 МСК');
      await expect(replies.nth(1).locator('time')).toHaveText('19.11.2026, 10:00');
      await expect(replies.nth(0).getByText(run.card.title, { exact: true })).toBeVisible();
      await expect(replies.nth(1)).not.toContainText(run.card.title);
      await expect(replies.nth(1).getByText('Оценка прежнего назначения', { exact: true })).toBeVisible();
      await expect(page.locator('#dashboard-appeals')).not.toContainText(run.model.readiness.assignment_ref);
      await replies.nth(0).getByText('Ваше обращение', { exact: true }).click();
      expect(await replies.nth(0).evaluate(el => el.scrollWidth <= el.clientWidth + 1)).toBe(true);
      await replies.nth(2).getByText('Ваше обращение', { exact: true }).click();
      await expect(replies.nth(2).getByText('Связь с оценкой неизвестна')).toBeVisible();
      await expect(page.locator('#completed-assessments article')).toHaveCount(1);
      await expect(page.locator('#completed-assessments article')).toContainText('Результат готов');
      const geometry = await page.locator('#dashboard-panel').evaluate((node) => {
        const css = getComputedStyle(node), card = node.querySelector('.participant-assessment-card');
        return { background: css.backgroundColor, card: getComputedStyle(card).borderRadius,
          scroll: document.documentElement.scrollWidth, width: document.documentElement.clientWidth,
          font: getComputedStyle(card).fontFamily, fontsLoaded: document.fonts.check('16px Onest') };
      });
      expect(geometry.background).toBe('rgb(247, 247, 247)');
      expect(geometry.card).toBe('8px'); expect(geometry.scroll).toBe(geometry.width);
      expect(geometry.fontsLoaded).toBe(true);
      if (evidence) await fs.writeFile(path.join(evidence, `geometry-${width}.json`), JSON.stringify(geometry, null, 2));
      if (width === 1440) {
        run.journey.readFailure = true;
        await page.locator('#dashboard-refresh-button').evaluate((button) => button.click());
        await expect(page.locator('#dashboard-refresh-status')).toBeVisible();
        await expect(page.locator('#current-assessments')).toContainText('3 ситуация из 8');
        run.journey.readFailure = false;
        run.card.completed_positions = null;
        await page.locator('#dashboard-refresh-button').click();
        await expect(page.locator('#dashboard-refresh-status')).toBeHidden();
        await expect(page.getByRole('progressbar', { name: 'Завершено ситуаций' })).toHaveCount(0);
      }
      if (width !== 320) {
        // Opening the selected active Cycle preserves the existing explicit return barrier.
        await page.locator('#assessment-action-button').click();
        const returnCard = page.locator('.interview-return-card');
        await expect(returnCard.getByRole('heading')).toHaveText('Продолжим оценку?');
        await expect(returnCard).toContainText('Вы остановились на ситуации 3 из 8.');
        await expect(page.locator('#interview-timer-badge')).toContainText('20:00');
        await expect(returnCard.getByRole('button', { name: 'Продолжить' })).toBeInViewport();
        await expect(page.locator('#interview-textarea')).toBeDisabled();
        if (evidence) await page.screenshot({ path: path.join(evidence, `assessment-return-${width}.png`) });
        expect(run.calls.filter((call) => call.pathname.endsWith('/runtime'))).toEqual([]);
        await page.goto(`${base}/?screen=dashboard`);
        await expect(page.locator('#dashboard-panel')).toBeVisible();
        // A ready card opens the saved ready screen. Entry and logo/link return are reads.
        run.card.status = 'prepared'; run.card.journey_state = 'ready'; run.card.current_position_no = null;
        run.card.action = 'open_readiness'; run.card.button_label = 'Приступить к оценке'; run.card.status_label = 'Готова к началу';
        await page.locator('#dashboard-refresh-button').evaluate((button) => button.click());
        await expect(page.locator('#current-assessments')).toContainText('Готова к началу');
        await page.locator('#assessment-action-button').click();
        await expect(page.locator('#onboarding-title')).toHaveText('Ваши кейсы подготовлены');
        await expect(page.locator('.onboarding-metrics')).toContainText('8');
        await expect(page.locator('#feature-list')).toContainText('Сохранённый методологический notice.');
        await page.getByRole('button', { name: 'Мои оценки', exact: true }).click();
        await expect(page.locator('#dashboard-panel')).toBeVisible();
        // A card cannot open another assignment's ready plan after a scope change.
        run.model.prepared_plan.cycle_id = 'different-cycle';
        run.model.prepared_plan.start_readiness.cycle_id = 'different-cycle';
        await page.locator('#assessment-action-button').click();
        await expect(page.locator('#onboarding-title')).toHaveText('Состояние оценки изменилось');
        await page.locator('#onboarding-home').click();
        await expect(page.locator('#dashboard-panel')).toBeVisible();
        // Returning to a preparing card must also avoid resolve/prepare commands.
        run.model.prepared_plan = null; run.model.preparation_operation = { operation_id: 'owned-op', status: 'queued' };
        run.card.journey_state = 'preparing'; run.card.status_label = 'Оценка готовится';
        await page.locator('#dashboard-refresh-button').evaluate((button) => button.click());
        await expect(page.locator('#current-assessments')).toContainText('Оценка готовится');
        await page.locator('#assessment-action-button').click();
        await expect(page.locator('#onboarding-title')).toHaveText('Готовим вашу оценку');
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
        // Read-only history and return must not create a missing preparation operation.
        run.model.preparation_operation = null; run.journey.next_action = 'show_onboarding';
        await page.locator('#onboarding-view-history').click();
        await page.locator('#onboarding-next').click();
        await expect(page.locator('#onboarding-title')).toHaveText('Готовим вашу оценку');
        await page.locator('#onboarding-home').click();
        await expect(page.locator('#dashboard-panel')).toBeVisible();
      }
      if (width !== 320) {
        run.dashboard.current_assessments = [];
        await page.locator('#dashboard-refresh-button').evaluate((button) => button.click());
        await expect(page.locator('#current-assessments')).toContainText('Пока нет назначенных оценок');
        await expect(page.locator('.participant-assessment-card[data-cycle-id="previous-cycle"]')).toHaveCount(1);
        await expect(page.locator('#completed-assessments article')).toHaveCount(1);
      }
      expect(run.calls.filter((call) => /\/assessment\/.+(start|prepare|continue)|resolve-profile/.test(call.pathname))).toEqual([]);
      expect(run.calls.filter((call) => call.method !== 'GET')).toEqual([]);
      expect(run.unexpected).toEqual([]); expect(errors).toEqual([]);
      if (evidence) await fs.writeFile(path.join(evidence, `requests-${width}.json`), JSON.stringify(run.calls, null, 2));
    }
    await progress(`done-${width}`);
  });
}
