// One isolated fixture, production frontend and substituted HTTP only; no DB/LLM/mail.
import { test, expect } from '@playwright/test';
import fs from 'node:fs/promises';
import http from 'node:http';
import path from 'node:path';
let server, base;
const evidence = 'docs/evc/tasks/p4k-postw02-04/evidence';
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
    completed_cases: null, total_cases: 8, planned_total: 8, current_position_no: 3, plan_revision_id: 'saved-plan', calendar_deadline: '2026-11-19T12:00:00Z' };
  const dashboard = { current_assessments: [card], completed_assessments: [{ ...card, cycle_id: 'previous-cycle', current_position_no: null,
    title: 'Предыдущее прохождение', status: 'report_ready', journey_state: 'report_ready', status_label: 'Результат готов',
    description: 'Результат доступен.', action: 'open_report', button_label: 'Посмотреть результат', report_id: 'saved-report', calendar_deadline: null, closed_at: '2026-11-10T12:00:00Z' }] };
  const model = { assignment_id: 91, assessment_name: card.title, readiness: { status: 'ready', organization_id: 10, assignment_ref: 'cabinet', questionnaire_revision_id: 41,
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
    if (pathname === '/users/8/journey-state') return respond(route, { next_action: journey.next_action, can_open_dashboard: true,
      profile: { status: 'complete' }, onboarding: model.onboarding, assessment: { status: 'in_progress', runtime_kind: 'cycle', cycle_id: card.cycle_id } });
    if (pathname.startsWith('/users/assessment/cycles/preparation/')) return respond(route, model.preparation_operation);
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

const saved = { operation_id: 'synthetic-preparation', kind: 'assessment', status: 'running',
  stage_label: 'Проверяем материалы ситуации', explanation: 'Проверяем, что ситуацию можно открыть для прохождения.',
  started_at: '2026-11-16T11:30:00Z', stage_started_at: '2026-11-16T11:33:00Z',
  last_progress_at: '2026-11-16T11:33:00Z', read_at: '2026-11-16T12:00:00Z',
  freshness: 'confirmed', delayed: true, delay_notice_seconds: 300, reference: 'P4K-1234567890ABCDEF12345678', allowed_actions: ['check'] };
for (const width of [1440,390]) test(`04 detailed status, reload, read error and admin ${width}`, async ({ page, context }) => {
  await context.grantPermissions(['clipboard-read','clipboard-write']);
  await page.setViewportSize({ width, height: width === 1440 ? 1000 : 844 });
  await page.clock.install({ time: new Date('2026-11-16T12:00:00Z') });
  const errors=[]; page.on('pageerror', e => errors.push(e.message));
  const run=await fixture(page);
  Object.assign(run.card, { status: 'prepared', journey_state: 'preparing', action: 'open_readiness',
    status_label: 'Подготовка оценки', button_label: 'Посмотреть состояние', preparation: saved });
  run.model.prepared_plan=null;
  run.model.preparation_operation={ operation_id: saved.operation_id, status:'running', preparation:saved };
  await page.goto(base);
  await page.locator('#assessment-action-button').click();
  await expect(page.locator('#onboarding-panel [data-preparation-stage]')).toContainText(saved.stage_label);
  await page.getByText('Посмотреть знакомство',{exact:true}).click();
  await expect(page.locator('#onboarding-panel [data-preparation-status]')).toHaveCount(0);
  run.journey.next_action='show_onboarding';
  await page.getByRole('button',{name:'Вернуться к готовности оценки',exact:true}).click();
  run.journey.next_action='show_dashboard';
  await expect(page.locator('#onboarding-panel [data-preparation-stage]')).toContainText(saved.stage_label);
  const root=page.locator('#onboarding-panel [data-preparation-status]');
  await expect(root.locator('[data-preparation-duration]')).toContainText('30 мин.');
  await root.locator('summary').click();
  await root.getByRole('button',{name:'Скопировать сведения'}).click();
  const clipboard=await page.evaluate(() => navigator.clipboard.readText());
  expect(clipboard).toContain(saved.reference); expect(clipboard).toContain('27 мин.');
  expect(clipboard).not.toMatch(/operation_id|attempt_token|SQL|JSON/);
  await page.screenshot({path:`${evidence}/preparation-${width}.png`,fullPage:true});
  await root.getByRole('button',{name:'Скопировать сведения'}).focus();
  await page.clock.fastForward(60001);
  await expect(root.getByRole('button',{name:'Скопировать сведения'})).toBeFocused();
  await expect(root.locator('[data-preparation-duration]')).toContainText('31 мин.');
  expect(await root.locator('[aria-live]').count()).toBe(0);
  expect(await page.evaluate(()=>document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
  await page.reload();
  await expect(page.locator('#dashboard-panel')).toBeVisible();
  await page.locator('#assessment-action-button').click();
  await expect(page.locator('#onboarding-panel [data-preparation-stage]')).toContainText(saved.stage_label);
  expect(run.calls.filter(c=>c.method==='POST')).toEqual([]);
  await page.route('**/users/assessment/cycles/preparation/**', route=>route.abort('failed'));
  await page.locator('#onboarding-next').click();
  await expect(page.locator('#onboarding-panel [data-preparation-notice]')).toContainText('последние полученные сведения');
  await page.screenshot({path:`${evidence}/read-error-${width}.png`,fullPage:true});
  await page.unroute('**/users/assessment/cycles/preparation/**');
  const nextPreparation={...saved,operation_id:'synthetic-next',kind:'next',stage_label:'Готовим следующую ситуацию',
    explanation:'Подготавливаем условие и материалы следующего задания.'};
  run.model.preparation_operation={operation_id:'synthetic-next',status:'running',preparation:nextPreparation};
  run.journey.next_action='resume_assessment';
  await page.route('**/users/assessment/m7/cycles/cabinet-cycle/return-state',route=>route.fulfill({json:{cycle_id:'cabinet-cycle',allowed_action:'connected'}}));
  await page.route('**/users/assessment/cycles/cabinet-cycle/runtime',route=>route.fulfill({json:{
    cycle_id:'cabinet-cycle',status:{collection_status:'paused',remaining_seconds:7200},between_situations:true,
    participant_progress:{planned_total:8,last_completed_position_no:2},route:{positions:[],progress:{total_positions:8}},
    preparation_operation:run.model.preparation_operation,situations:[],trace:{turns:[],events:[]}}}));
  await page.goto(`${base}/?screen=interview`);
  const nextRoot=page.locator('#interview-panel [data-preparation-status]');
  await expect(nextRoot).toContainText('Готовим следующую ситуацию');
  await nextRoot.locator('summary').click();
  await nextRoot.getByRole('button',{name:'Скопировать сведения'}).focus();
  await page.clock.fastForward(2000);
  await expect(nextRoot.getByRole('button',{name:'Скопировать сведения'})).toBeFocused();
  await page.getByRole('button',{name:'Проверить состояние',exact:true}).click();
  await expect(nextRoot).toContainText('Готовим следующую ситуацию');
  await page.screenshot({path:`${evidence}/next-preparation-${width}.png`,fullPage:true});
  run.journey.next_action='show_dashboard';
  await page.unroute('**/users/assessment/m7/cycles/cabinet-cycle/return-state');
  await page.unroute('**/users/assessment/cycles/cabinet-cycle/runtime');
  const reportPreparation = { ...saved, kind:'report', stage_label:'Собираем отчёт', explanation:'Оформляем результаты и пояснения.' };
  const reportModel = { collection_status:'collection_closed', results_status:'processing', report_status:'not_created', preparation:reportPreparation };
  let reportReads=0, reportReadError=false;
  await page.route('**/users/assessment/m8/cycles/cabinet-cycle/status',route=>{
    reportReads+=1;
    return reportReadError ? route.abort('failed') : route.fulfill({json:reportModel});
  });
  Object.assign(run.card,{action:'open_processing',status:'collection_closed',preparation:reportPreparation});
  await page.goto(base);
  await expect(page.locator('#dashboard-panel')).toBeVisible();
  await page.locator('#assessment-action-button').click();
  const reportRoot=page.locator('#processing-panel [data-preparation-status]');
  await expect(reportRoot).toContainText('Собираем отчёт');
  await reportRoot.locator('summary').click();
  await reportRoot.getByRole('button',{name:'Скопировать сведения'}).focus();
  await page.clock.fastForward(61000);
  await expect(reportRoot.getByRole('button',{name:'Скопировать сведения'})).toBeFocused();
  const exhausted=reportReads;
  await page.clock.fastForward(120000);
  expect(reportReads).toBe(exhausted);
  await page.getByRole('button',{name:'Проверить состояние',exact:true}).click();
  await expect.poll(()=>reportReads).toBe(exhausted+1);
  await page.screenshot({path:`${evidence}/report-preparation-${width}.png`,fullPage:true});
  reportReadError=true;
  await page.getByRole('button',{name:'Проверить состояние',exact:true}).click();
  await expect(reportRoot.locator('[data-preparation-notice]')).toContainText('последние полученные сведения');
  reportReadError=false;
  Object.assign(reportModel,{results_status:'ready',report_status:'ready',partial_result:{is_incomplete:true},
    preparation:{...reportPreparation,status:'ready',stage_label:'Отчёт готов'}});
  await page.getByRole('button',{name:'Повторить проверку',exact:true}).click();
  await expect(page.getByRole('button',{name:'Посмотреть результат',exact:true})).toBeVisible();
  await expect(reportRoot).toContainText('Отчёт готов');
  expect(run.calls.filter(c=>c.method==='POST')).toEqual([]);
  await page.unroute('**/users/**');
  await page.unroute('**/users/assessment/m8/cycles/cabinet-cycle/status');
  const { startAdminProgramPreview } = await import('../../scripts/adm-program-ui-preview.mjs');
  const admin=await startAdminProgramPreview({port:18965});
  try {
    await page.route('**/users/admin/organizations',async route=>{
      const response=await route.fetch(); const data=await response.json();
      data.items[0].members[0].assessment_stages={'synthetic-pilot-11': {code:'preparing',label:'Идёт подготовка оценки',
        action:'check_preparation',assignment_id:91,preparation:saved}};
      await route.fulfill({response,json:data});
    });
    await page.goto(`${admin.base}/demo/admin/confirmed/`);
    if(await page.locator('#admin-open-organizations-button').isVisible()) await page.locator('#admin-open-organizations-button').click();
    const card=page.locator('[data-organization-id="3"]');
    await expect(card).toBeVisible();
    await card.locator('.admin-organization-step[data-view="people"]').click();
    const adminRoot=card.locator('[data-preparation-status]').first();
    await expect(adminRoot).toContainText(saved.stage_label);
    await adminRoot.locator('summary').click();
    await expect(adminRoot).toContainText(saved.reference);
    await adminRoot.getByRole('button',{name:'Скопировать сведения'}).click();
    expect(await page.evaluate(()=>navigator.clipboard.readText())).toContain(saved.reference);
    await page.screenshot({path:`${evidence}/admin-${width}.png`,fullPage:true});
    expect(await page.evaluate(()=>document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
    expect(errors).toEqual([]);
  } finally { await admin.close(); }
});
