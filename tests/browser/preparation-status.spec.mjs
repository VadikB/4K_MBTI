// One isolated fixture, production frontend and substituted HTTP only; no DB/LLM/mail.
import { test, expect } from '@playwright/test';
import fs from 'node:fs/promises';
import http from 'node:http';
import path from 'node:path';
let server, base;
const evidence = process.env.POSTW02_EVIDENCE || 'docs/evc/tasks/p4k-postw02-04/evidence/review';
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
const fits = async (page, width) => {
  expect(await page.evaluate(()=>document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
  const actions = page.locator('[data-preparation-actions] button:visible, [data-preparation-status] summary:visible');
  for (const action of await actions.all()) {
    const rect=await action.boundingBox();
    expect(rect.x).toBeGreaterThanOrEqual(0); expect(rect.x+rect.width).toBeLessThanOrEqual(width+1);
  }
};
const snap = async (page, name, width) => {
  await fits(page,width);
  await page.screenshot({path:`${evidence}/${name}-${width}.png`,fullPage:true,scale:'css'});
};
const details = async (page, root, name, width) => {
  await expect(root.locator('details')).not.toHaveAttribute('open');
  await expect(root.locator('[data-preparation-copied]')).toBeEmpty();
  await root.locator('summary').click();
  await expect(root.locator('[data-preparation-reference]')).toBeVisible();
  await expect(root).toContainText('Номер подготовки');
  await root.getByRole('button',{name:'Скопировать сведения'}).click();
  await expect(root.locator('[data-preparation-copied]')).toHaveText('Сведения скопированы');
  const copied=await page.evaluate(()=>navigator.clipboard.readText());
  expect(copied).toContain(await root.locator('[data-preparation-reference]').innerText());
  expect(copied).not.toMatch(/operation_id|attempt_token|JSON|SQL|prompt|Cycle/);
  await snap(page,`${name}-details`,width);
};
for (const width of [1440,390,320]) test(`04 review real screens ${width} CSS px`, async ({page,context}) => {
  await context.grantPermissions(['clipboard-read','clipboard-write']);
  await page.setViewportSize({width,height:width===1440?1000:844});
  await page.clock.install({time:new Date('2026-11-16T12:00:00Z')});
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  const run=await fixture(page);
  Object.assign(run.card,{status:'prepared',journey_state:'preparing',action:'open_readiness',status_label:'Подготовка оценки',button_label:'Посмотреть состояние',preparation:saved});
  run.model.prepared_plan=null;
  run.model.preparation_operation={operation_id:saved.operation_id,status:'running',preparation:saved};
  await page.goto(base);
  const compact=page.locator('#dashboard-panel [data-preparation-status]').first();
  await expect(compact).toHaveClass(/preparation-status--compact/);
  await expect(compact.locator('[data-preparation-reference]')).not.toBeVisible();
  await snap(page,'dashboard',width);
  await page.locator('#assessment-action-button').click();
  const root=page.locator('#onboarding-panel [data-preparation-status]');
  await expect(root.locator('[data-preparation-stage]')).toHaveText(saved.stage_label);
  await expect(root).not.toHaveClass(/is-failed/);
  await expect(root.locator('[data-preparation-duration]')).toContainText('Подготовка: 30 мин · Этап без изменений: 27 мин');
  await expect(page.getByRole('heading',{name:'Готовим вашу оценку',exact:true})).toBeVisible();
  await snap(page,'preparation',width);
  await details(page,root,'preparation',width);
  await root.getByRole('button',{name:'Скопировать сведения'}).focus();
  await page.clock.fastForward(60001);
  await expect(root.locator('details')).toHaveAttribute('open','');
  await expect(root.getByRole('button',{name:'Скопировать сведения'})).toBeFocused();
  await expect(root.locator('[data-preparation-duration]')).toContainText('31 мин');
  await page.reload();
  await page.locator('#assessment-action-button').click();
  await expect(root.locator('details')).not.toHaveAttribute('open');
  // Successful acquaintance receipt -> failed preparation read -> successful read.
  await page.route('**/users/assessment/cycles/preparation/**',route=>route.abort('failed'));
  await page.locator('#onboarding-next').click();
  await expect(root.locator('[data-preparation-notice]')).toContainText('Показаны последние полученные сведения');
  await expect(root.locator('[data-preparation-stage]')).toContainText('Последний известный этап');
  await expect(page.locator('#onboarding-panel')).toContainText('ваши ответы сохранены');
  await snap(page,'preparation-read-error',width);
  await page.unroute('**/users/assessment/cycles/preparation/**');
  await page.locator('#onboarding-next').click();
  await expect(root.locator('[data-preparation-notice]')).not.toContainText('Не удалось обновить');
  await expect(root.locator('[data-preparation-duration]')).toContainText('31 мин');
  // Next situation uses saved full-plan position and confirmed blocking wait.
  const nextPreparation={...saved,reference:'P4K-ABCDEF1234567890ABCDEF12',kind:'next',stage_label:'Готовим следующую ситуацию',explanation:'Подготавливаем условие и материалы следующего задания.'};
  run.model.preparation_operation={operation_id:'synthetic-next',status:'running',preparation:nextPreparation};
  run.journey.next_action='resume_assessment';
  let runtimeReadError=false;
  const runtime={cycle_id:'cabinet-cycle',status:{collection_status:'active',remaining_seconds:7200},between_situations:true,blocking_system_wait:true,
    participant_progress:{planned_total:8,last_completed_position_no:2},route:{positions:[],progress:{total_positions:8}},
    preparation_operation:run.model.preparation_operation,situations:[],trace:{turns:[],events:[]}};
  await page.route('**/users/assessment/m7/cycles/cabinet-cycle/return-state',route=>route.fulfill({json:{cycle_id:'cabinet-cycle',allowed_action:'connected'}}));
  await page.route('**/users/assessment/cycles/cabinet-cycle/runtime',route=>runtimeReadError?route.abort('failed'):route.fulfill({json:runtime}));
  await page.goto(`${base}/?screen=interview`);
  const nextRoot=page.locator('#interview-panel [data-preparation-status]');
  await expect(nextRoot).toContainText('Готовим следующую ситуацию');
  await expect(page.locator('#interview-panel')).toContainText('Ситуация 2 завершена');
  await expect(page.locator('#interview-section-title')).toBeVisible();
  await expect(page.locator('#interview-profile-button')).toBeVisible();
  await expect(page.locator('#interview-panel')).toContainText('Время на ответы сейчас не расходуется');
  await snap(page,'next-preparation',width);
  await details(page,nextRoot,'next-preparation',width);
  runtimeReadError=true;
  await page.clock.fastForward(2100);
  await expect(nextRoot.locator('[data-preparation-notice]')).toContainText('Не удалось обновить состояние');
  await expect(page.locator('#interview-error')).not.toContainText('Сохранение введённого текста');
  await expect(page.locator('#interview-panel')).toContainText('Ответы сохранены');
  runtimeReadError=false;
  await page.getByRole('button',{name:'Проверить состояние',exact:true}).click();
  await expect(nextRoot.locator('[data-preparation-notice]')).not.toContainText('Не удалось обновить состояние');
  await expect(nextRoot.locator('details')).toHaveAttribute('open','');
  expect(run.calls.filter(c=>c.method==='POST')).toEqual([]);
  // The actual report waiting screen; all read states are distinct.
  run.journey.next_action='show_dashboard';
  await page.unroute('**/users/assessment/m7/cycles/cabinet-cycle/return-state');
  await page.unroute('**/users/assessment/cycles/cabinet-cycle/runtime');
  const reportPreparation={...saved,reference:'P4K-333333333333333333333333',kind:'report',stage_label:'Собираем отчёт',explanation:'Оформляем результаты и пояснения.'};
  const reportModel={collection_status:'collection_closed',results_status:'processing',report_status:'not_created',preparation:reportPreparation};
  let reportReads=0,reportReadError=false,hold=null;
  await page.route('**/users/assessment/m8/cycles/cabinet-cycle/status',async route=>{
    reportReads++;
    if(hold){ const wait=hold;hold=null;await wait.promise;return route.fulfill({json:wait.value}); }
    return reportReadError?route.abort('failed'):route.fulfill({json:reportModel});
  });
  Object.assign(run.card,{action:'open_processing',status:'collection_closed',preparation:reportPreparation});
  await page.goto(base);await page.locator('#assessment-action-button').click();
  const reportRoot=page.locator('#processing-panel [data-preparation-status]');
  await expect(reportRoot).toContainText('Собираем отчёт');
  await expect(page.locator('#processing-outcome-title')).toHaveText('Спасибо за ваши ответы');
  await expect(page.locator('#processing-outcome-status')).toBeEmpty();
  await snap(page,'report-preparation',width);
  await details(page,reportRoot,'report-preparation',width);
  // Clipboard rejection is honest, and focus/open details survive status updates.
  await page.evaluate(()=>{window.originalClipboardWrite=navigator.clipboard.writeText.bind(navigator.clipboard);navigator.clipboard.writeText=async()=>{throw new Error('denied');};});
  await reportRoot.getByRole('button',{name:'Скопировать сведения'}).click();
  await expect(reportRoot.locator('[data-preparation-copied]')).toContainText('Не удалось скопировать');
  await page.evaluate(()=>{navigator.clipboard.writeText=window.originalClipboardWrite;});
  const check=page.getByRole('button',{name:'Проверить состояние',exact:true});
  await page.clock.fastForward(61000);
  const exhausted=reportReads;await page.clock.fastForward(120000);expect(reportReads).toBe(exhausted);
  reportReadError=true;await check.click();
  await expect(reportRoot.locator('[data-preparation-notice]')).toContainText('Показаны последние полученные сведения');
  await snap(page,'report-read-error',width);
  reportReadError=false;reportPreparation.freshness='unconfirmed';
  // Refresh timestamps with controlled time while preserving operation start.
  reportPreparation.read_at=await page.evaluate(()=>new Date().toISOString());
  await check.click();
  await expect(reportRoot.locator('[data-preparation-notice]')).toHaveText('Сейчас не можем подтвердить, что подготовка продолжается');
  await snap(page,'report-unconfirmed',width);
  reportPreparation.freshness='confirmed';reportPreparation.delayed=false;
  // A separate normal-work fixture, with internally consistent persisted times.
  reportPreparation.reference='P4K-444444444444444444444444';
  reportPreparation.started_at=new Date(Date.parse(reportPreparation.read_at)-180000).toISOString();
  reportPreparation.stage_started_at=reportPreparation.last_progress_at=new Date(Date.parse(reportPreparation.read_at)-60000).toISOString();
  await check.click();await expect(reportRoot.locator('[data-preparation-notice]')).toBeEmpty();
  await snap(page,'report-normal',width);
  await page.clock.fastForward(100000);
  await expect(reportRoot.locator('[data-preparation-stage]')).toContainText('Последний известный этап');
  await expect(reportRoot.locator('[data-preparation-duration]')).toContainText('на момент обновления');
  await snap(page,'report-stale',width);
  reportPreparation.read_at=await page.evaluate(()=>new Date().toISOString());
  reportPreparation.status='failed';reportPreparation.finished_at=reportPreparation.read_at;
  reportModel.results_status='failed';await check.click();
  await expect(reportRoot.locator('[data-preparation-notice]')).toHaveText('Не удалось завершить подготовку отчёта.');
  await expect(page.locator('#processing-outcome-indicator')).toHaveClass(/is-error/);
  reportReadError=true;await check.click();
  await expect(reportRoot.locator('[data-preparation-notice]')).toContainText('Не удалось завершить подготовку отчёта.');
  await expect(reportRoot.locator('[data-preparation-notice]')).toContainText('Не удалось обновить состояние');
  await snap(page,'report-failed-read-error',width);
  // A later read wins; an older outstanding response cannot return the page to waiting.
  reportReadError=false;
  let release;const promise=new Promise(resolve=>{release=resolve;});
  hold={promise,value:{...reportModel,results_status:'processing',preparation:{...reportPreparation,status:'running',read_at:'2026-11-16T12:00:00Z'}}};
  const heldAt=reportReads;await check.click();await expect.poll(()=>reportReads).toBe(heldAt+1);
  Object.assign(reportModel,{results_status:'ready',report_status:'ready',partial_result:{is_incomplete:true},preparation:{...reportPreparation,status:'ready',stage_label:'Отчёт готов'}});
  await check.click();await expect(page.getByRole('button',{name:'Посмотреть результат',exact:true})).toBeVisible();
  release();await page.waitForTimeout(50);
  await expect(page.getByRole('button',{name:'Посмотреть результат',exact:true})).toBeVisible();
  await snap(page,'report-ready',width);
  expect(run.calls.filter(c=>c.method==='POST')).toEqual([]);
  await page.unroute('**/users/**');await page.unroute('**/users/assessment/m8/cycles/cabinet-cycle/status');
  // Linked assignment and absent assignment are separate, consistent member fixtures.
  const {startAdminProgramPreview}=await import('../../scripts/adm-program-ui-preview.mjs');
  const admin=await startAdminProgramPreview({port:18965});
  try {
    let adminError=false;
    await page.route('**/users/admin/organizations/3/questionnaire',route=>route.fulfill({json:{items:[{id:41,organization_id:3,assignment_ref:'synthetic-pilot-11',status:'confirmed',effective_confirmed:{id:41},answers_json:{},validation_json:{}}]}}));
    await page.route('**/users/admin/organizations',async route=>{
      if(adminError)return route.abort('failed');
      const response=await route.fetch();const data=await response.json();
      data.items[0].members_count=3;
      const member=data.items[0].members[0];
      Object.assign(member,{full_name:'Синтетический участник с длинным именем для проверки переноса',has_password:true,registration_status:'registered',assessment_assignments:['synthetic-pilot-11'],
        assessment_stages:{'synthetic-pilot-11':{code:'preparing',label:'Идёт подготовка оценки',action:'check_preparation',assignment_id:91,preparation:{...saved,read_at:await page.evaluate(()=>new Date().toISOString())}}}});
      data.items[0].members.push({...member,user_id:29,email:'absent@example.test',full_name:'Участник без назначения',assessment_assignments:[],assessment_stages:{'synthetic-pilot-12':{code:'preparing',preparation:{...saved,reference:'P4K-FFFFFFFFFFFFFFFFFFFFFFFF'}}}});
      data.items[0].members.push({...member,user_id:30,email:'cancelled@example.test',full_name:'Участник с отменённым назначением',assessment_assignments:[],assessment_stages:{'synthetic-pilot-11':{code:'cancelled',label:'Назначение отменено',assignment_id:40,preparation:saved}}});
      await route.fulfill({response,json:data});
    });
    for(const role of (width===320?['admin','superadmin']:['admin'])) {
      await page.goto(`${admin.base}/demo/${role}/confirmed/`);
      if(await page.locator('#admin-open-organizations-button').isVisible())await page.locator('#admin-open-organizations-button').click();
      const card=page.locator('[data-organization-id="3"]');await expect(card).toBeVisible();
      await card.locator('.admin-organization-step[data-view="people"]').click();
      const member=card.locator('.admin-organization-member').filter({hasText:'member@example.test'});
      const adminRoot=member.locator('[data-preparation-status]');
      await expect(member).not.toContainText('назначения нет');
      await expect(card.locator('.admin-organization-member').filter({hasText:'absent@example.test'})).toContainText('Для выбранной оценки назначения нет');
      await expect(card.locator('.admin-organization-member').filter({hasText:'absent@example.test'}).locator('[data-preparation-status]')).toHaveCount(0);
      const cancelled=card.locator('.admin-organization-member').filter({hasText:'cancelled@example.test'});
      await expect(cancelled).toContainText('Назначение отменено');
      await expect(cancelled.locator('[data-preparation-status]')).toHaveCount(0);
      await expect(adminRoot).toHaveClass(/preparation-status--compact/);
      await snap(page,role,width);
      await member.screenshot({path:`${evidence}/${role}-card-${width}.png`,scale:'css'});
      await details(page,adminRoot,role,width);
      await member.screenshot({path:`${evidence}/${role}-card-details-${width}.png`,scale:'css'});
      const detailBox=await adminRoot.locator('.preparation-details').boundingBox(),memberBox=await member.boundingBox();
      expect(detailBox.width).toBeGreaterThan(memberBox.width*0.7);
      await adminRoot.getByRole('button',{name:'Скопировать сведения'}).focus();
      // Refresh uses existing tenant GET and preserves intentional disclosure/focus.
      await page.evaluate(async(entry)=>{const m=await import('/web/dist/'+entry);await m.refreshAdminOrganizationsSafely();},(await fs.readdir('web/dist')).find(name=>name.startsWith('admin-organizations-')));
      await expect(adminRoot.locator('details')).toHaveAttribute('open','');
      await expect(adminRoot.getByRole('button',{name:'Скопировать сведения'})).toBeFocused();
      adminError=true;
      await member.locator('[data-action="check-member-preparation"]').click();
      await expect(adminRoot.locator('[data-preparation-notice]')).toContainText('Не удалось обновить состояние');
      adminError=false;
      await member.locator('[data-action="check-member-preparation"]').click();
      await expect(adminRoot.locator('[data-preparation-notice]')).not.toContainText('Не удалось обновить состояние');
      expect((await(await page.request.get(`${admin.base}/__preview/requests`)).json()).filter(r=>r.method!=='GET')).toEqual([]);
      for(const tab of await card.locator('.admin-organization-step').all()) {
        await tab.scrollIntoViewIfNeeded();await expect(tab).toBeVisible();
      }
    }
    expect(errors).toEqual([]);
  }finally{await admin.close();}
});
