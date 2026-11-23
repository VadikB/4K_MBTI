import { test, expect } from '@playwright/test';
import http from 'node:http';
import fs from 'node:fs/promises';
import path from 'node:path';
const evidence=process.env.QA02_EVIDENCE || 'docs/evc/tasks/p4k-postw02-qa-02/evidence';
let server,base;
const deferred=()=>{let resolve;const promise=new Promise(r=>{resolve=r;});return {promise,resolve};};
test.beforeAll(async()=>{
  await fs.mkdir(evidence,{recursive:true});
  server=http.createServer(async(req,res)=>{try{
    const pathname=new URL(req.url,'http://localhost').pathname;
    const filename=path.join(process.cwd(),pathname==='/'?'web/index.html':pathname);
    res.setHeader('Content-Type',{'.html':'text/html','.js':'application/javascript','.css':'text/css','.svg':'image/svg+xml','.woff':'font/woff'}[path.extname(filename)]||'application/octet-stream');
    res.end(await fs.readFile(filename));
  }catch{res.statusCode=404;res.end('missing');}});
  await new Promise(r=>server.listen(0,'127.0.0.1',r));base=`http://127.0.0.1:${server.address().port}`;
});
test.afterAll(async()=>{if(server?.listening)await new Promise(r=>server.close(r));await fs.writeFile(`${evidence}/browser-cleanup.json`,JSON.stringify({listening:server?.listening,mail:0,llm:0}));});
async function setup(page,{superadmin=false,mixed=false}={}){
  const op='qa02-'+ 'x'.repeat(170);
  const members=Array.from({length:3},(_,i)=>({user_id:i+8,email:`person${i}@example.test`,full_name:`Участник ${i+1}`,has_password:false,
    registration_status:'pending',invitation_id:i+1,invitation_status:mixed?'not_sent':i===2?'accepted':'error',
    invitation_delivery_status:mixed?'not_sent':i===2?'accepted':'error',invitation_link_status:mixed?'not_created':'active',
    invitation_operation_id:mixed?null:op,invitation_assignment_ref:mixed?null:'competencies_4k',
    invitation_created_at:'2026-11-17T12:00:00Z',invitation_expires_at:'2026-11-20T12:00:00Z',
    invitation_reason:mixed?{}:{reason_code:i===2?'accepted':'mail_not_configured',next_action:i===2?'none':'operator'}}));
  const program={organization_id:3,program_definition_id:7,program_name:'Синтетическая программа',program_version:'1',assignment_ref:'competencies_4k',roles:[]};
  const org={id:3,code:'qa02',name:'Синтетическая организация',is_active:true,domains:[],admins:[],members_count:3,reports_count:0,members,assessment_program:program};
  const run={posts:[],reads:[],unknown:mixed,refreshGate:null};
  const user={id:18,email:'admin@example.test',full_name:'Администратор'};
  await page.route('**/users/**',async route=>{
    const req=route.request(),url=new URL(req.url()),p=url.pathname;
    const json=(body,status=200)=>route.fulfill({status,contentType:'application/json',body:JSON.stringify(body)});
    if(p==='/users/session/restore')return json({authenticated:false});
    if(p==='/users/version')return json({version:'2.1.28'});
    if(p==='/users/auth/email/request-link')return json({email:user.email,auth_mode:'password'});
    if(p==='/users/auth/email/password-login')return json({exists:true,user,is_admin:true,agent:{session_id:'admin',message:'',stage:'admin',completed:true},admin_dashboard:{metrics:[],insights:[],activity_series:[],competency_average:[]}});
    if(p==='/users/admin/organizations')return json({is_superadmin:superadmin,items:[org]});
    if(p.endsWith('/questionnaire'))return json({items:[{id:11,assignment_ref:'competencies_4k',status:'confirmed',channel:'product_form',validation_json:{},briefing:{},readiness:{early:{status:'ready',message:'Ранний минимум подтверждён'},context:{status:'ready'},roles:{status:'ready'},preparation:{status:'idle'}}}]});
    if(p.endsWith('/personal-invitations')&&req.method()==='POST'){
      run.posts.push(req.postDataJSON());return route.abort('failed');
    }
    if(p.includes('/personal-invitations/operations/')){
      run.reads.push(p);
      if(run.refreshGate){await run.refreshGate.promise;run.refreshGate=null;}
      const selected=url.searchParams.getAll('email');
      return json({items:members.filter(m=>!selected.length||selected.includes(m.email)).map((m,i)=>({email:m.email,invitation_id:m.invitation_id,
        status:run.unknown?(i===0?'accepted':i===1?'error':'uncertain'):'accepted',delivery_status:run.unknown?(i===0?'accepted':i===1?'error':'sending'):'accepted',
        reason_code:run.unknown?(i===1?'provider_recipient':'delivery_unknown'):'accepted',link_status:'active',created_at:m.invitation_created_at,expires_at:m.invitation_expires_at}))});
    }
    return json({},404);
  });
  await page.goto(base);await page.locator('#email-input').fill(user.email);await page.locator('#request-magic-link-button').click();
  await page.locator('#magic-token-input').fill('synthetic-password');await page.locator('#verify-magic-link-button').click();
  await expect(page.locator('#admin-organizations-panel')).toBeVisible();
  if (superadmin) await page.locator('#platform-org-rows [data-org-id="3"]:not([data-org-admins])').click();
  return run;
}
for(const width of [1440,390,320])test(`QA02 details and common failure at ${width}`,async({page,context})=>{
  test.setTimeout(20000);await page.setViewportSize({width,height:1000});await context.grantPermissions(['clipboard-read','clipboard-write']);
  const run=await setup(page,{superadmin:width===1440});
  await expect(page.locator('.admin-invitation-common')).toHaveCount(1);
  await expect(page.locator('.admin-invitation-common')).toContainText('сервис отправки не настроен');
  await expect(page.locator('.admin-organization-member').first()).not.toContainText('проверьте адрес');
  await page.locator('[data-action="open-member-card"]').first().click();
  const dialog=page.locator('.admin-member-card-dialog'),details=dialog.locator('.admin-invitation-details');
  await expect(details).toBeVisible();await expect(details).not.toHaveAttribute('open','');
  await expect(details.locator('[data-invite-case]')).toHaveText('INV-1');
  await details.locator('summary').focus();await page.keyboard.press('Enter');await expect(details).toHaveAttribute('open','');
  const gate=deferred();run.refreshGate=gate;
  await details.getByRole('button',{name:'Обновить сведения'}).click();
  await expect(details.locator('[data-invite-read-status]')).toHaveText('Проверяем эту попытку');
  await details.locator('summary').click();gate.resolve();
  await expect(details.locator('[data-invite-diagnostic]')).toHaveText('Письмо принято почтовым сервисом');
  await expect(details).not.toHaveAttribute('open','');
  await details.locator('summary').click();
  const gate2=deferred();run.refreshGate=gate2;
  await details.getByRole('button',{name:'Обновить сведения'}).click();
  await details.locator('summary').click();await details.locator('summary').click();gate2.resolve();
  await expect(details.getByRole('button',{name:'Обновить сведения'})).toBeEnabled();await expect(details).toHaveAttribute('open','');
  await details.getByRole('button',{name:'Копировать сведения'}).click();await expect(details.locator('[data-invite-read-status]')).toHaveText('Сведения скопированы');
  expect(await page.evaluate(()=>navigator.clipboard.readText())).toContain('qa02-');
  expect(await page.evaluate(()=>document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
  expect(await details.evaluate(e=>e.scrollWidth<=e.clientWidth)).toBe(true);
  await page.screenshot({path:`${evidence}/details-${width}.png`,fullPage:true});
  await dialog.getByRole('button',{name:'Закрыть карточку'}).click();
  await page.locator('[data-action="open-member-card"]').nth(1).click();await expect(page.locator('.admin-invitation-details')).not.toHaveAttribute('open','');
  await page.locator('.admin-member-card-dialog').getByRole('button',{name:'Закрыть карточку'}).click();
  await page.screenshot({path:`${evidence}/common-failure-${width}.png`,fullPage:true});
  expect(run.posts).toHaveLength(0);
});
test('QA02 mixed lost response recovers the same command without duplicate',async({page})=>{
  test.setTimeout(20000);const run=await setup(page,{mixed:true});
  const organization = page.locator('[data-organization-id="3"]');
  await expect(organization.locator('[data-admin-view="questionnaire"]')).toContainText('Ранний минимум подтверждён');
  await organization.getByRole('checkbox', { name: 'Выбрать доступных' }).check();
  await expect(organization.locator('input[name="invitation_email"]:checked')).toHaveCount(3);
  await organization.locator('[data-action="send-member-invitations"] button').click();
  await expect(page.locator('#admin-organizations-status')).toContainText('Приняты сервисом: 1. Не отправлены: 1. Исход уточняется: 1');
  expect(run.posts[0].emails).toEqual(['person0@example.test', 'person1@example.test', 'person2@example.test']);
  const id=run.posts[0].operation_id;run.unknown=false;
  await page.getByRole('button',{name:'Проверить отправку',exact:true}).first().click();
  await expect(page.locator('#admin-organizations-status')).toContainText('Приняты сервисом: 3. Не отправлены: 0. Исход уточняется: 0');
  expect(run.posts).toHaveLength(1);expect(run.reads.every(p=>p.endsWith('/'+id))).toBe(true);
  await page.screenshot({path:`${evidence}/mixed-recovered-1440.png`,fullPage:true});
});

test('QA02 late detail response never updates another participant card',async({page})=>{
  test.setTimeout(20000);const run=await setup(page);
  await page.locator('[data-action="open-member-card"]').first().click();
  const old=page.locator('.admin-member-card-dialog');await old.locator('.admin-invitation-details summary').click();
  const gate=deferred();run.refreshGate=gate;
  await old.getByRole('button',{name:'Обновить сведения'}).click();
  await expect(old.locator('[data-invite-read-status]')).toHaveText('Проверяем эту попытку');
  await old.getByRole('button',{name:'Закрыть карточку'}).click();
  await page.locator('[data-action="open-member-card"]').nth(1).click();
  gate.resolve();
  const next=page.locator('.admin-member-card-dialog');
  await expect(next.locator('h3')).toHaveText('Участник 2');
  await expect(next.locator('.admin-invitation-details')).not.toHaveAttribute('open','');
  await next.locator('.admin-invitation-details summary').click();
  await expect(next.locator('[data-invite-diagnostic]')).toContainText('сервис отправки не настроен');
});

test('UX-06 sent invitation actions stay with the organization administrator', async ({ page }) => {
  const run = await setup(page);
  const participant = page.locator('[data-member-user-id="10"]');
  const menu = participant.locator('.admin-organization-member-menu');
  const trigger = menu.locator('summary');
  for (const width of [1440, 390, 320]) {
    await page.setViewportSize({ width, height: width === 1440 ? 1000 : 844 });
    await trigger.focus();
    await page.keyboard.press('Enter');
    await expect(menu.getByRole('menuitem', { name: 'Отправить письмо повторно' })).toBeVisible();
    await expect(menu.getByRole('menuitem', { name: 'Отозвать приглашение' })).toBeVisible();
    await page.evaluate(() => document.fonts.ready);
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
    const bounds = await menu.getByRole('menu').boundingBox();
    expect(bounds.x).toBeGreaterThanOrEqual(0);
    expect(bounds.x + bounds.width).toBeLessThanOrEqual(width + 1);
    await page.screenshot({ path: `${evidence}/menu-sent-${width}.png`, fullPage: true, scale: 'css' });
    await page.keyboard.press('Escape');
    await expect(menu).not.toHaveAttribute('open', '');
    await expect(trigger).toBeFocused();
  }
  expect(run.posts).toHaveLength(0);
});
