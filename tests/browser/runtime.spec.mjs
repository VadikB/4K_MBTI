import { test as base, expect } from '@playwright/test';
import { spawn, spawnSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { randomUUID } from 'node:crypto';
const root=process.cwd(), python=process.env.BROWSER_PYTHON || path.join(root,'.venv/bin/python');
const fixture=JSON.parse(fs.readFileSync('tests/browser/fixtures/v1.json','utf8'));
const test=base.extend({context:async({browser},use)=>{
 const context=await browser.newContext({viewport:{width:1440,height:1000},locale:'ru-RU',acceptDownloads:true});
 try{await use(context);}finally{await context.close();}
},stand:async({},use,info)=>{
  if(!process.env.STAND_ADMIN_URL) throw new Error('Explicit isolated STAND_ADMIN_URL required');
  const dir=path.join(root,'.test-stand/browser',randomUUID());fs.mkdirSync(dir,{recursive:true});
  const statePath=path.join(dir,'state.json'),port=18830;
  const cli=(action)=>{const r=spawnSync(python,['scripts/test_stand.py',action,'--state',statePath,'--port',String(port),'--gateway','1'],{encoding:'utf8'});fs.appendFileSync(path.join(dir,'prepare.log'),r.stdout+r.stderr);if(r.status!==0)throw new Error(action+': '+r.stderr);};
  let server;
  cli('create');
  try{
    cli('bootstrap');
    {const inputs=JSON.parse(fs.readFileSync(statePath));inputs.qa_orchestration=true;inputs.browser_scenario='acceptance-v1';fs.writeFileSync(statePath,JSON.stringify(inputs));}
    if(info.title.includes('character')){const inputs=JSON.parse(fs.readFileSync(statePath));inputs.browser_case='character';fs.writeFileSync(statePath,JSON.stringify(inputs));}
    if((info.title.includes('REV-02') || info.title.includes('P10.5') || info.title.includes('G10.7'))){const inputs=JSON.parse(fs.readFileSync(statePath));inputs.browser_profile='unprepared';fs.writeFileSync(statePath,JSON.stringify(inputs));}
    if(info.title.includes('no admitted catalog')){const inputs=JSON.parse(fs.readFileSync(statePath));inputs.browser_catalog='unavailable';fs.writeFileSync(statePath,JSON.stringify(inputs));}
    cli('seed');
    const variant=info.title.includes('C1')?'budget':info.title.includes('C2')?'deadline':'ordinary';
    const prep=spawnSync(python,['scripts/browser_stand.py','--state',statePath,'--variant',variant],{encoding:'utf8'});
    if(prep.status!==0)throw new Error(prep.stderr);
    const fd=fs.openSync(path.join(dir,'app.log'),'a');
    server=spawn(python,['scripts/test_stand.py','serve','--state',statePath],{stdio:['ignore',fd,fd]});fs.closeSync(fd);
    const url=`http://127.0.0.1:${port}`;
    await expect.poll(async()=>{try{return (await fetch(url+'/health/ready')).status}catch{return 0}},{timeout:30000}).toBe(200);
    const state=JSON.parse(fs.readFileSync(statePath,'utf8'));
    await use({url,state,dir});
  }finally{
    if(server && server.exitCode===null){const ended=new Promise(resolve=>server.once('exit',resolve));server.kill('SIGTERM');await ended;}
    cli('destroy');
    await info.attach('server-log',{path:path.join(dir,'app.log'),contentType:'text/plain'});
  }
}});
test.beforeEach(async({page,stand,browser},info)=>{
 page.acceptanceDir=stand.dir;page.acceptanceNetwork=[];
 await page.setViewportSize({width:1440,height:1000});
 await info.attach('browser-version',{body:browser.version(),contentType:'text/plain'});
 page.on('response',async response=>{
   const url=new URL(response.url());
   if(!url.pathname.startsWith('/users/assessment/') || response.request().method()!=='POST')return;
   try{page.acceptanceNetwork.push({at:new Date().toISOString(),path:url.pathname,status:response.status(),response:await response.json()});}catch{}
 });
});
test.afterEach(async({page},info)=>{
 await info.attach('assessment-http',{body:JSON.stringify(page.acceptanceNetwork||[],null,2),contentType:'application/json'});
});
async function login(page,stand,email='participant@example.test',prepare=false,navigate=true){
 if(!page.acceptanceDialogHandler){page.on('dialog',dialog=>dialog.accept());page.acceptanceDialogHandler=true;}
 page.on('response',async response=>{try{if(response.url().endsWith('/runtime') && response.ok()){page.acceptanceCycle=(await response.json()).cycle_id;}}catch{/* Navigation may discard diagnostic response bodies. */}});
 if(navigate) await page.goto(stand.url);
 await page.locator('#email-input').fill(email);
 await page.locator('#request-magic-link-button').click();
 await page.locator('#magic-token-input').fill(stand.state.password);
 await page.locator('#verify-magic-link-button').click();
 const continueButton=page.getByRole('button',{name:'Продолжить',exact:true});
 await expect(continueButton).toBeVisible();
 await continueButton.click();
 const confirm=page.getByRole('button',{name:'Подтвердить профиль',exact:true});
 await expect(confirm).toBeVisible();
 await expect(confirm).toBeEnabled();
 if(prepare){
   const options=await (await page.request.get(stand.url+'/users/assessment/profile/options')).json();
   expect(options.current_profile).toBeNull();
   await page.locator('[name="role_profile_version_id"]').selectOption({label:'Менеджер проекта, продукта или процесса · версия 1'});
   await page.locator('[name="position"]').fill('Эксперт по программам');
   await page.locator('[name="duties"]').fill('Согласовать план разработки программ');
   await test.info().attach('profile-confirmation',{body:await page.screenshot({fullPage:true}),contentType:'image/png'});
 }
 await confirm.click();
 await expect(page.locator('#assessment-action-button')).toBeVisible();
}
test('Same-domain email outside the exact allowlist is denied',async({page,stand})=>{
 await page.goto(stand.url);
 await page.locator('#email-input').fill('outside@example.test');
 const denied=page.waitForResponse(response=>new URL(response.url()).pathname==='/users/auth/email/request-link');
 await page.locator('#request-magic-link-button').click();
 expect((await denied).status()).toBe(403);
 await expect(page.locator('#auth-error')).toBeVisible();
 await expect(page.locator('#auth-token-form')).toBeHidden();
});
test('Organization invitation keeps context and cannot admit a member of another organization',async({page,stand})=>{
 const invitation=`browser-invitation-${stand.state.run_id}`;
 await page.goto(`${stand.url}/?invite=${encodeURIComponent(invitation)}`);
 await expect(page.locator('#organization-invitation-context')).toContainText('Синтетическая организация E10.2');
 await expect(page.locator('#organization-invitation-context')).toContainText('Техническое приглашение');
 await page.reload();
 await expect(page.locator('#organization-invitation-context')).toContainText('Синтетическая организация E10.2');
 await page.locator('#email-input').fill('member-b@example.test');
 const denied=page.waitForResponse(response=>new URL(response.url()).pathname==='/users/auth/email/request-link');
 await page.locator('#request-magic-link-button').click();
 expect((await denied).status()).toBe(403);
 await expect(page.locator('#auth-error')).toContainText('выбранной организации');
 await expect(page.locator('#auth-token-form')).toBeHidden();
});
async function start(page,expected='готовности'){
 await page.locator('#assessment-action-button').click();
 await page.locator('#prechat-start-button').click();
 await expect(page.locator('#interview-textarea')).toBeEnabled({timeout:15000});
 await expect(page.locator('#interview-messages')).toContainText(expected);
 await test.info().attach('interview-start',{body:await page.screenshot({fullPage:true}),contentType:'image/png'});
}
async function answer(page,text=fixture.answer){await page.locator('#interview-textarea').fill(text);await page.locator('#interview-submit-button').click();await expect(page.locator('#interview-submit-button')).toBeEnabled({timeout:30000});await expect(page.locator('#interview-error')).toBeHidden();await expect(page.locator('#interview-messages .own')).toContainText([text]);}
async function report(page,stand,info){
 await expect(page.locator('#report-panel')).toBeVisible({timeout:70000});
 await expect(page.locator('#m8-report-state')).toContainText('Report готов',{timeout:70000});
 const cycle=new URL(page.url()).searchParams.get('cycle_id');expect(cycle).toBeTruthy();
 const response=await page.request.get(`${stand.url}/users/assessment/m8/cycles/${cycle}/reports/latest`);expect(response.ok()).toBeTruthy();const saved=await response.json();
 const downloadPromise=page.waitForEvent('download');await page.locator('#report-download-button').click();
 const download=await downloadPromise;const pdf=path.join(stand.dir,'report.pdf');await download.saveAs(pdf);
 expect(fs.readFileSync(pdf).subarray(0,4).toString()).toBe('%PDF');
 await info.attach('report-pdf',{path:pdf,contentType:'application/pdf'});
 fs.writeFileSync(path.join(stand.dir,'report.json'),JSON.stringify(saved,null,2));
 await info.attach('report',{path:path.join(stand.dir,'report.json'),contentType:'application/json'});
 const checked=spawnSync(python,['scripts/verify_browser_pdf.py',pdf,path.join(stand.dir,'report.json')],{encoding:'utf8'});
 expect(checked.status,checked.stderr).toBe(0);
 await info.attach('pdf-content-check',{body:checked.stdout,contentType:'text/plain'});
 await page.screenshot({path:path.join(stand.dir,'report.png'),fullPage:true});
 await info.attach('report-ui',{path:path.join(stand.dir,'report.png'),contentType:'image/png'});
 await page.reload();await expect(page.locator('#m8-report-state')).toContainText('Report готов');
 expect(await (await page.request.get(`${stand.url}/users/assessment/m8/cycles/${cycle}/reports/latest`)).json()).toEqual(saved);
 return saved;
}
test('S10-A and T11-10 positive, clarification and saved Report/PDF',async({page,stand},info)=>{
 await login(page,stand);await start(page);await answer(page);
 const dialogue=await runtime(page,stand);
 const delivered=dialogue.trace.events.find(x=>x.event_type==='mandatory_update');
 expect(delivered).toBeTruthy();expect(delivered.sequence_no).toBeGreaterThan(dialogue.trace.turns[0].sequence_no);
 expect(JSON.stringify(dialogue)).not.toContain('execution_envelope');
 await page.locator('#interview-finish-button').click();
 await expect(page.locator('#interview-messages')).toContainText(fixture.question,{timeout:30000});
 await info.attach('clarification-ui',{body:await page.screenshot({fullPage:true}),contentType:'image/png'});
 await answer(page,fixture.clarification_answer);
 await expect(page.locator('#interview-finish-button')).toBeEnabled({timeout:30000});
 await page.locator('#interview-finish-button').click();
 const saved=await report(page,stand,info);
 const resultResponse=await page.request.get(`${stand.url}/users/assessment/m8/cycles/${saved.cycle_id}/results`);
 expect(resultResponse.ok()).toBeTruthy();const results=await resultResponse.json();
 await info.attach('saved-results',{body:JSON.stringify(results,null,2),contentType:'application/json'});
 const mixed=results.results.observations.filter(x=>['K1.I16','K1.I17'].includes(x.indicator_id));
 expect(mixed.map(x=>x.outcome)).toEqual(['INSUFFICIENT_EVIDENCE','L1']);
 const scored=saved.c67.skills.filter(x=>x.skill_result_exists);
 expect(scored.map(x=>x.skill_id)).toEqual(['K1.3','K1.4']);
 for(const skill of scored){expect(skill.outcome).toBe('partial_score');expect(skill.score).toEqual({value:1,numerator:1,denominator:1});expect(skill.skill_level).toBeUndefined();}
 expect(saved.c67.coverage.full_m2.admissible_contributions.numerator).toBe(2);
 expect(saved.c67.coverage.full_m2.admissible_contributions.denominator).toBe(61);
 expect(saved.c67.recommendations.filter(x=>x.skill_id==='K1.4').map(x=>x.type)).toEqual(['Development']);
 expect(saved.c67.recommendations.map(x=>x.type)).toEqual(expect.arrayContaining(['Development','Consolidation / Maintenance','Application / Transfer']));
 for(const r of saved.c67.recommendations){
   expect(r.basis_refs.length).toBeGreaterThan(0);
   for(const basis of r.basis_refs){expect(basis.cycle_id).toBe(saved.cycle_id);expect(basis.results_revision_id).toBe(saved.results_revision_id);expect(basis.outcome).toBe('L1');expect(basis.material_excerpts[0].quote).toBe(fixture.answer);}
   await expect(page.locator('#report-panel')).toContainText(r.goal);
 }
 const other=await page.context().browser().newContext();const second=await other.newPage();await login(second,stand,'other@example.test');
 for(const endpoint of [`/users/assessment/m8/cycles/${saved.cycle_id}/results`,`/users/assessment/m8/cycles/${saved.cycle_id}/reports/latest`,`/users/assessment/m8/reports/${saved.id}/pdf`])expect((await second.request.get(stand.url+endpoint)).status()).toBe(403);
 await other.close();
 // N3/N4: rare saved-history/failure fixtures only after the full positive browser path.
 for(const kind of ['legacy','failure']){
   const prep=spawnSync(python,['scripts/browser_report_fixture.py','--state',path.join(stand.dir,'state.json'),'--cycle',saved.cycle_id,'--kind',kind],{encoding:'utf8'});
   expect(prep.status,prep.stderr).toBe(0);
   await page.reload();
   const dir=path.join(stand.dir,kind);fs.mkdirSync(dir);
   const rare=await report(page,{...stand,dir},info);
   expect(rare.results_revision_id).toBe(saved.results_revision_id);expect(rare.c67.recommendations).toHaveLength(0);
   expect(rare.c67.skills).toEqual(saved.c67.skills);
   if(kind==='failure')expect(rare.c67.recommendation_generation.status).toBe('failed');
   await expect(page.locator('#report-panel')).not.toContainText('Недопустимое историческое проявление');
   const url=`${stand.url}/users/assessment/m8/cycles/${saved.cycle_id}/reports/regenerate`,data={idempotency_key:'browser-regenerate-'+kind};
   const freshResponse=await page.request.post(url,{data});expect(freshResponse.status()).toBe(201);const fresh=await freshResponse.json();
   expect(fresh.revision_no).toBe(rare.revision_no+1);expect(fresh.results_revision_id).toBe(saved.results_revision_id);
   expect((await (await page.request.post(url,{data})).json()).id).toBe(fresh.id);
   expect(fresh.c67.recommendations).toEqual(saved.c67.recommendations);
 }

});
async function runtime(page,stand){
 const cycle=new URL(page.url()).searchParams.get('cycle_id') || page.acceptanceCycle;
 // cycle_id is also published by the start response; read-only lookup is not progression.
 if(cycle)return (await page.request.get(`${stand.url}/users/assessment/cycles/${cycle}/runtime`)).json();
 const response=await page.waitForResponse(r=>r.url().endsWith('/runtime'));
 return response.json();
}
test('S10-B interruption and Additional Session preserve Cycle and deadline',async({page,stand},info)=>{
 await login(page,stand);await start(page);await answer(page);
 const first=await runtime(page,stand);
 await page.locator('#interview-additional-button').click();
 await expect(page.locator('#interview-case-status')).toContainText('Сессия прервана');
 await page.reload();
 await expect(page.locator('#interview-additional-button')).toHaveText('Продолжить в дополнительной сессии');
 await page.locator('#interview-additional-button').click();
 await expect(page.locator('#interview-textarea')).toBeEnabled();
 const second=await runtime(page,stand);
 expect(second.cycle_id).toBe(first.cycle_id);
 expect(second.status.calendar_deadline).toBe(first.status.calendar_deadline);
 expect(second.status.remaining_seconds).toBeLessThanOrEqual(first.status.remaining_seconds);
 expect(second.current_situation.assessment_situation_id).not.toBe(first.current_situation.assessment_situation_id);
 expect(second.trace.turns).toHaveLength(0);
 await answer(page,'Синтетический ответ второй ситуации: уточняю условия и предлагаю согласовать следующий шаг.');
 await page.locator('#interview-finish-button').click();
 await expect(page.locator('#interview-messages')).toContainText(fixture.question,{timeout:30000});
 await answer(page,'Уточняю смысл своего предыдущего ответа: сначала проверить условия передачи.');
 await expect(page.locator('#interview-finish-button')).toBeEnabled({timeout:30000});await page.locator('#interview-finish-button').click();
 const saved=await report(page,stand,info);expect(saved.c67.sessions).toHaveLength(2);
 expect(new Set(saved.c67.sessions.map(x=>x.session_id)).size).toBe(2);
 const denied=await page.request.post(`${stand.url}/users/assessment/m7/cycles/${first.cycle_id}/additional-sessions`,{data:{intent_id:second.continuation.intent_id,idempotency_key:'after-close'}});
 expect(denied.status()).toBe(409);
 const newCycle=await page.request.post(stand.url+'/users/assessment/cycles/start',{data:{idempotency_key:randomUUID(),selected_skills:['K1','K2','K3','K4']}});
 expect(newCycle.ok()).toBeTruthy();expect((await newCycle.json()).runtime.cycle_id).not.toBe(first.cycle_id);
 expect((await (await page.request.get(`${stand.url}/users/assessment/m8/cycles/${first.cycle_id}/reports/latest`)).json()).id).toBe(saved.id);
});
for(const variant of ['C1','C2']) test(`S10-${variant} background time closure without another Turn`,async({page,context,stand},info)=>{
 test.setTimeout(240000);
 await login(page,stand);await start(page);await answer(page);
 const before=await runtime(page,stand);
 await info.attach('runtime-before-expiry',{body:JSON.stringify(before,null,2),contentType:'application/json'});
 if(variant==='C2'){
   await page.locator('#interview-pause-button').click();await expect(page.locator('#interview-pause-button')).toHaveText('Продолжить');
   await page.close();page=await context.newPage();
 }else{
   page.acceptanceCdp=await context.newCDPSession(page);
   await page.acceptanceCdp.send('Page.setWebLifecycleState',{state:'frozen'});
   await info.attach('background-visibility',{body:JSON.stringify({at:new Date().toISOString(),lifecycle:'frozen'}),contentType:'application/json'});
 }
 const statusUrl=`${stand.url}/users/assessment/m7/cycles/${before.cycle_id}`;
 // Allow the 30s fixture budget, the 30s worker sweep and result calculation on CI.
 await expect.poll(async()=>{const r=await context.request.get(statusUrl);return (await r.json()).collection_status;},{timeout:120000,intervals:[500,1000]}).toBe('calculated');
 await info.attach('runtime-after-expiry',{body:JSON.stringify(await (await context.request.get(statusUrl)).json(),null,2),contentType:'application/json'});
 const late=await context.request.post(`${stand.url}/users/assessment/m5/situations/${before.current_situation.assessment_situation_id}/turns`,{data:{request_id:'late',turn_id:randomUUID(),content:'Late synthetic answer'}});expect(late.status()).toBe(409);
 await info.attach('late-turn',{body:JSON.stringify({status:late.status(),response:await late.json()}),contentType:'application/json'});
 if(variant==='C1'){
   await page.acceptanceCdp.send('Page.setWebLifecycleState',{state:'active'});
   await page.acceptanceCdp.detach();
 }
 await page.bringToFront();
 await page.goto(`${stand.url}/?screen=interview&cycle_id=${before.cycle_id}`);
 const saved=await report(page,stand,info);
 expect(saved.c67.collection.reason).toBe(variant==='C1'?'time_budget':'calendar_deadline');
 const trace=await (await page.request.get(`${stand.url}/users/assessment/m5/situations/${before.current_situation.assessment_situation_id}/trace`)).json();
 expect(trace.turns.filter(x=>x.speaker_type==='assessee')).toHaveLength(1);
});
test('Recovery: lost response, unaccepted request, two tabs and owner boundaries',async({page,context,stand})=>{
 await login(page,stand);await start(page);
 const initial=await runtime(page,stand);
 expect(JSON.stringify(initial)).not.toContain('execution_envelope');
 for(const accepted of [true,false]){
   const seen=[];let first=true;
   await page.route('**/users/assessment/m5/situations/*/turns',async route=>{
     seen.push(route.request().postDataJSON());
     if(first){first=false;if(accepted)await route.fetch();await route.abort('failed');}
     else await route.continue();
   });
   await page.locator('#interview-textarea').fill(fixture.answer);
   await page.locator('#interview-submit-button').click();
   await expect(page.locator('#interview-error')).toBeVisible();
   await page.locator('#interview-submit-button').click();
   await expect(page.locator('#interview-error')).toBeHidden();
   await expect(page.locator('#interview-submit-button')).toBeEnabled();
   expect(seen).toHaveLength(2);expect(seen[1]).toEqual(seen[0]);
   await page.unroute('**/users/assessment/m5/situations/*/turns');
 }
 const saved=await runtime(page,stand);expect(saved.trace.turns.filter(x=>x.speaker_type==='assessee')).toHaveLength(2);
 const tab=await context.newPage();await tab.goto(page.url());
 await expect(tab.locator('#interview-messages .own')).toHaveCount(2);
 await page.reload();await expect(page.locator('#interview-messages .own')).toHaveCount(2);
 const startAgain=await context.request.post(stand.url+'/users/assessment/cycles/start',{data:{idempotency_key:randomUUID(),selected_skills:['K1','K2','K3','K4']}});
 expect((await startAgain.json()).runtime.cycle_id).toBe(initial.cycle_id);
 await page.getByRole('button',{name:'Выйти',exact:true}).click();
 await expect(page.locator('#email-input')).toBeVisible();
 await login(page,stand,'other@example.test');
 for(const endpoint of [`/users/assessment/cycles/${initial.cycle_id}/runtime`,`/users/assessment/m5/situations/${initial.current_situation.assessment_situation_id}/trace`])expect((await page.request.get(stand.url+endpoint)).status()).toBe(403);
 await expect(page.locator('#interview-messages')).not.toBeVisible();
});
test('Late 401 in another tab must not revoke a newly authenticated owner',async({page,context,stand})=>{
 await login(page,stand);await start(page);
 const tab=await context.newPage();await tab.goto(page.url());
 await expect(tab.locator('#interview-textarea')).toBeEnabled();
 let captured,fetchExpired,releaseExpired;
 const capturedRequest=new Promise(resolve=>{captured=resolve;});
 const fetchGate=new Promise(resolve=>{fetchExpired=resolve;});
 const deliveryGate=new Promise(resolve=>{releaseExpired=resolve;});
 let expired;
 const expiredResponse=new Promise(resolve=>{expired=resolve;});
 await tab.route('**/users/assessment/cycles/*/runtime',async route=>{
   captured();await fetchGate;
   const response=await route.fetch();
   expired(response.status());await deliveryGate;
   await route.fulfill({response});
 });
 try{
   await capturedRequest;
   await page.getByRole('button',{name:'Выйти',exact:true}).click();
   await expect(page.locator('#email-input')).toBeVisible();
   fetchExpired();expect(await expiredResponse).toBe(401);
   await login(page,stand,'other@example.test');
   let backgroundLogouts=0;
   tab.on('request',request=>{if(new URL(request.url()).pathname==='/users/session/logout')backgroundLogouts++;});
   releaseExpired();
   await expect(tab.locator('#email-input')).toBeVisible();
   // Synchronize with completion of the stale response recovery, including any logout.
   await tab.waitForLoadState('networkidle');
   expect(backgroundLogouts).toBe(0);
   const restored=await (await page.request.get(stand.url+'/users/session/restore')).json();
   expect(restored.authenticated).toBe(true);
   expect(restored.user.email).toBe('other@example.test');
 }finally{fetchExpired();releaseExpired();await tab.close();}
});
test('S10-A character branch: actual character Turn, order and no invented recommendation',async({page,stand},info)=>{
 await login(page,stand);await start(page,'Нина');
 const before=await runtime(page,stand);
 expect(before.trace.turns).toHaveLength(0);
 expect(before.plan.plan.catalog.find(x=>x.case_id==='CASE-TDISC-04').reasons).toContain('CASE_UNRESOLVED_DECISIONS');
 expect(JSON.stringify(before)).not.toContain(fixture.character_response);
 await answer(page,fixture.character_answer);
 await expect(page.locator('#interview-messages')).toContainText(fixture.character_response);
 const after=await runtime(page,stand);
 const own=after.trace.turns.find(x=>x.speaker_type==='assessee'),character=after.trace.turns.find(x=>x.speaker_type==='character');
 expect(character.speaker_name).toBe('Нина, новый сотрудник');
 const characterBubble=page.locator(`[data-turn-id="${character.turn_id}"] .interview-bubble`);
 await expect(characterBubble).toHaveAttribute('data-speaker-label',character.speaker_name);
 expect(await characterBubble.evaluate(el=>getComputedStyle(el,'::before').content)).toContain(character.speaker_name);
 expect(character.content_text).toBe(fixture.character_response);expect(character.sequence_no).toBeGreaterThan(own.sequence_no);
 await page.locator('#interview-finish-button').click();
 await expect(page.locator('#interview-messages')).toContainText(fixture.character_question,{timeout:30000});
 await info.attach('character-and-clarification-ui',{body:await page.screenshot({fullPage:true}),contentType:'image/png'});
 await answer(page,'Я предложил проверить запрос и остановиться при отличии условий от инструкции.');
 await expect(page.locator('#interview-finish-button')).toBeEnabled();await page.locator('#interview-finish-button').click();
 const saved=await report(page,stand,info);expect(saved.c67.recommendations).toHaveLength(0);
 expect(saved.c67.recommendation_generation.status).toBe('unavailable');
});


test('REV-02 fresh M4 confirmation, canonical context and saved history after login', async({page,stand},info)=>{
 test.setTimeout(240000);
 await login(page,stand,'participant@example.test',true);
 await start(page);await answer(page);
 await page.locator('#interview-finish-button').click();
 await expect(page.locator('#interview-messages')).toContainText(fixture.question,{timeout:30000});
 await answer(page,fixture.clarification_answer);
 await page.locator('#interview-finish-button').click();
 const saved=await report(page,stand,info);
 const results=await (await page.request.get(`${stand.url}/users/assessment/m8/cycles/${saved.cycle_id}/results`)).json();
 expect(results.results.personalized_profile_snapshot.content.user_context.position_or_status).toBe('Эксперт по программам');
 expect(saved.c67.recommendations.length).toBeGreaterThan(0);
 const selection=saved.c67.recommendation_generation.input.context_selection;
 expect(selection.status).toBe('available');
 expect(selection.selected_path).toBe('user_context.regular_tasks');
 for(const item of saved.c67.recommendations)expect(item.application_context).toContain(selection.value);
 expect(saved.c67.recommendation_generation.input.profile_projection.organization_context.activity_description).toBe('Техническая проверка');
 await info.attach('canonical-results',{body:JSON.stringify(results,null,2),contentType:'application/json'});
 const regenerated=await page.request.post(`${stand.url}/users/assessment/m8/cycles/${saved.cycle_id}/reports/regenerate`,{data:{idempotency_key:'review-history-revision'}});
 expect(regenerated.status()).toBe(201);const latest=await regenerated.json();expect(latest.id).not.toBe(saved.id);
 // Ordinary logout, then a new login and the dashboard history entry.
 await page.locator('#report-back-button').click();
 await page.locator('#dashboard-panel .user-chip').click();
 await page.locator('#dashboard-restart-button').click();
 await login(page,stand);
 await expect(page.locator('.reports-summary-count')).toHaveText('1');
 await page.locator('.reports-summary-button').click();
 const card=page.locator('.cycle-report');await expect(card).toHaveCount(1);
 await info.attach('history-list',{body:await page.screenshot({fullPage:true}),contentType:'image/png'});
 await expect(card.locator('option')).toHaveCount(2);
 await card.locator('select').selectOption(saved.id);
 await card.locator('.cycle-report-open').click();
 await expect(page.locator('#m8-report-state')).toContainText('Report готов');
 expect(new URL(page.url()).searchParams.get('report_id')).toBe(saved.id);
 const exact=await (await page.request.get(`${stand.url}/users/assessment/m8/reports/${saved.id}`)).json();expect(exact).toEqual(saved);
 await page.reload();await expect(page.locator('#m8-report-state')).toContainText('Report готов');
 expect(new URL(page.url()).searchParams.get('report_id')).toBe(saved.id);
 const downloaded=page.waitForEvent('download');await page.locator('#report-download-button').click();
 const pdf=path.join(stand.dir,'history.pdf');await (await downloaded).saveAs(pdf);
 const historyCheck=spawnSync(python,['scripts/verify_browser_pdf.py',pdf,path.join(stand.dir,'report.json')],{encoding:'utf8'});
 expect(historyCheck.status,historyCheck.stderr).toBe(0);
 await info.attach('history-pdf-check',{body:historyCheck.stdout,contentType:'text/plain'});
 await info.attach('history-pdf',{path:pdf,contentType:'application/pdf'});
 await info.attach('history-report',{body:await page.screenshot({fullPage:true}),contentType:'image/png'});
 // H10.6: a new independent Cycle remains a separate card, revisions stay inside the first.
 await page.locator('#report-back-button').click();
 await page.locator('#reports-back-button').click();
 await start(page); await answer(page);
 await page.locator('#interview-finish-button').click();
 await expect(page.locator('#interview-messages')).toContainText(fixture.question,{timeout:30000});
 await answer(page,fixture.clarification_answer);
 await page.locator('#interview-finish-button').click();
 const secondDir=path.join(stand.dir,'second-cycle'); fs.mkdirSync(secondDir);
 const second=await report(page,{...stand,dir:secondDir},info);
 expect(second.cycle_id).not.toBe(saved.cycle_id); expect(second.results_revision_id).not.toBe(saved.results_revision_id);
 await page.locator('#report-back-button').click();
 await page.locator('.reports-summary-button').click();
 await expect(page.locator('.cycle-report')).toHaveCount(2);
 const firstCard=page.locator(`.cycle-report[data-cycle-id="${saved.cycle_id}"]`);
 await expect(firstCard.locator('option')).toHaveCount(2);
 // Delay a real saved response, select a newer revision, then release the older response.
 let releaseOld; const oldGate=new Promise(resolve=>{releaseOld=resolve;});
 let capturedOld; const oldCaptured=new Promise(resolve=>{capturedOld=resolve;});
 await page.route(`**/users/assessment/m8/reports/${saved.id}`,async route=>{
   const response=await route.fetch(); capturedOld(); await oldGate; await route.fulfill({response});
 });
 await firstCard.locator('select').selectOption(saved.id); await firstCard.locator('.cycle-report-open').click();
 await oldCaptured;
 await page.locator('#report-back-button').click();
 await firstCard.locator('select').selectOption(latest.id); await firstCard.locator('.cycle-report-open').click();
 await expect(page.locator('#report-download-button')).toHaveAttribute('data-m8-report-id',latest.id);
 const oldDelivered=page.waitForResponse(response=>response.url().endsWith('/reports/'+saved.id));
 releaseOld(); await (await oldDelivered).finished(); await page.unrouteAll({behavior:'wait'});
 await expect(page.locator('#report-download-button')).toHaveAttribute('data-m8-report-id',latest.id);
 await page.locator('#report-back-button').click();
 await firstCard.locator('select').selectOption(saved.id);
 await firstCard.locator('.cycle-report-open').click();
 await expect(page.locator('#m8-report-state')).toContainText('версия представления 1');
 // A real synthetic legacy session coexists with both Cycles; its URL never retains Cycle IDs.
 const archive=spawnSync(python,['scripts/browser_report_fixture.py','--state',path.join(stand.dir,'state.json'),'--cycle',saved.cycle_id,'--kind','archive-session'],{encoding:'utf8'});
 expect(archive.status,archive.stderr).toBe(0);
 await page.locator('#report-back-button').click();
 await expect(page.locator('.cycle-report')).toHaveCount(2);
 // Bootstrap 10.2 does not claim a complete historical DDL. Only legacy screen
 // routing is simulated here; the mixed history above is read from the real DB.
 await page.route('**/users/*/assessment/*/skill-assessments',route=>route.fulfill({status:200,contentType:'application/json',body:'[]'}));
 await page.route('**/users/*/assessment/*/report-interpretation',route=>route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({insight_title:'Синтетический архив',insight_text:'Проверка маршрутизации',basis_items:[],growth_areas:[],has_interpretation_signal:false,has_confident_strongest:false,response_pattern:'synthetic'})}));
 await page.locator('.profile-history-item').click();
 await page.locator('.profile-history-report-button').click();
 await expect(page.locator('#legacy-report-shell')).toBeVisible();
 expect(new URL(page.url()).searchParams.has('cycle_id')).toBe(false);
 expect(new URL(page.url()).searchParams.has('report_id')).toBe(false);
 await expect(page.locator('#report-download-button')).toBeEnabled();
 await page.reload(); await expect(page.locator('#legacy-report-shell')).toBeVisible();
 await expect(page.locator('#m8-report-shell')).toBeHidden();
 await page.unrouteAll({behavior:'wait'});
 // Reload defaults legacy returnTarget to home; enter history through the dashboard again.
 await page.locator('#report-back-button').click(); await page.locator('.reports-summary-button').click();
 await expect(page.locator('.cycle-report')).toHaveCount(2);
 await info.attach('two-cycles-and-legacy',{body:await page.screenshot({fullPage:true}),contentType:'image/png'});
 await firstCard.locator('select').selectOption(saved.id); await firstCard.locator('.cycle-report-open').click();
 await expect(page.locator('#m8-report-state')).toContainText('версия представления 1');
 const otherTab=await page.context().newPage();
 await otherTab.goto(page.url());
 await expect(otherTab.locator('#m8-report-state')).toContainText('Report готов');
 await page.locator('#report-back-button').click(); await page.locator('#reports-back-button').click();
 await page.locator('#dashboard-panel .user-chip').click(); await page.locator('#dashboard-restart-button').click();
 await login(page,stand,'other@example.test');
 await otherTab.bringToFront(); await otherTab.evaluate(()=>window.dispatchEvent(new Event('focus')));
 await expect(otherTab.locator('#auth-panel')).toBeVisible();
 await expect(otherTab.locator('#m8-report-metadata')).toBeEmpty();
 await expect(otherTab.locator('#profile-history-list')).toBeEmpty();
 expect(await (await page.request.get(`${stand.url}/users/assessment/m8/history`)).json()).toMatchObject({cycles:[],reports_total:0});
 await otherTab.close();
});


test('S10.4 owner profile, 403, logout, late response and account switch',async({page,stand},info)=>{
 await login(page,stand);
 const settings=async()=>{await page.locator('#dashboard-panel .user-chip').click();await page.locator('#dashboard-profile-button').click();};
 await settings();
 await expect(page.locator('#profile-email')).toHaveValue('participant@example.test');
 await expect(page.locator('#profile-email')).toHaveAttribute('readonly','');
 await page.locator('#profile-telegram').fill('@owner_changed');await page.locator('#profile-telegram').press('Tab');
 await expect(page.locator('#profile-save-status')).toContainText('Telegram обновлен');
 await info.attach('owner-profile',{body:await page.screenshot({fullPage:true}),contentType:'image/png'});
 await page.reload();await expect(page.locator('#profile-telegram')).toHaveValue('@owner_changed');
 // Controlled 403 only checks UI handling; the same refusal is independently tested on real DB/router.
 await page.route('**/users/*/profile',async route=>route.fulfill({status:403,contentType:'application/json',body:JSON.stringify({detail:'Нет доступа к профилю.'})}));
 await page.locator('#profile-telegram').fill('@denied');await page.locator('#profile-telegram').press('Tab');
 await expect(page.locator('#profile-save-status')).toContainText('Нет доступа');
 await page.unroute('**/users/*/profile');
 await page.locator('#profile-back-button').click();
 let release;const gate=new Promise(resolve=>{release=resolve;});let captured;
 const capture=new Promise(resolve=>{captured=resolve;});
 await page.route('**/users/*/profile-summary',async route=>{
   const result=await route.fetch();captured();await gate;await route.fulfill({response:result});
 });
 await settings();await capture;
 await page.locator('#profile-back-button').click();
 await page.locator('#dashboard-panel .user-chip').click();await page.locator('#dashboard-restart-button').click();
 await expect(page.locator('#email-input')).toBeVisible();
 await expect(page.locator('#profile-email')).toHaveValue('');
 await expect(page.locator('#profile-name')).toHaveText('');
 await expect(page.locator('#profile-total-assessments')).toHaveText('0');
 await expect(page.locator('#profile-average-score')).toHaveText('0%');
 await login(page,stand,'other@example.test',false,false);
 release();await page.unrouteAll({behavior:'wait'});
 await settings();
 await expect(page.locator('#profile-email')).toHaveValue('other@example.test');
 await expect(page.locator('#profile-telegram')).toHaveValue('@synthetic_e102');
 await expect(page.locator('#profile-panel')).not.toContainText('Синтетический участник 1');
 await info.attach('other-profile',{body:await page.screenshot({fullPage:true}),contentType:'image/png'});
 // Missing/expired authentication uses the common 401 recovery and clears the profile.
 await page.context().clearCookies();
 await page.locator('#profile-telegram').fill('@expired');await page.locator('#profile-telegram').press('Tab');
 await expect(page.locator('#email-input')).toBeVisible();
 await expect(page.locator('#profile-email')).toHaveValue('');
});

function profileReceipts(stand) {
 const result=spawnSync(python,['scripts/inspect_profile_browser.py','--state',path.join(stand.dir,'state.json')],{encoding:'utf8'});
 expect(result.status,result.stderr).toBe(0);
 return JSON.parse(result.stdout);
}
test('P10.5 fresh profile, lost confirmation response, reload and first AS',async({page,stand},info)=>{
 const before=profileReceipts(stand);
 expect(before.profiles).toEqual([]);expect(before.user_context_count).toBe(0);expect(before.cycles).toEqual([]);
 let lost=true;
 await page.route('**/users/agent/profile/confirm',async route=>{
   if(!lost){await route.continue();return;}
   lost=false;
   const response=await route.fetch();expect(response.status()).toBe(200);
   await route.abort('failed');
 });
 // Keep the real first submit: the server commits but the browser loses its response.
 await page.goto(stand.url);
 await page.locator('#email-input').fill('participant@example.test');await page.locator('#request-magic-link-button').click();
 await page.locator('#magic-token-input').fill(stand.state.password);await page.locator('#verify-magic-link-button').click();
 await page.getByRole('button',{name:'Продолжить',exact:true}).click();
 await expect(page.getByRole('button',{name:'Подтвердить профиль',exact:true})).toBeEnabled();
 await page.locator('[name="full_name"]').fill('Синтетический участник приёмки');
 await page.locator('[name="position"]').fill('Эксперт по программам');
 await page.locator('[name="duties"]').fill('Согласовать план разработки программ');
 await page.locator('[name="role_profile_version_id"]').selectOption({label:'Менеджер проекта, продукта или процесса · версия 1'});
 await page.getByRole('button',{name:'Подтвердить профиль',exact:true}).click();
 await expect(page.locator('#chat-error')).toBeVisible();
 const committed=profileReceipts(stand);expect(committed.profiles).toHaveLength(1);
 await info.attach('lost-confirmation-response',{body:await page.screenshot({fullPage:true}),contentType:'image/png'});
 await page.getByRole('button',{name:'Подтвердить профиль',exact:true}).click();
 await expect(page.locator('#assessment-action-button')).toBeVisible();
 expect(profileReceipts(stand)).toEqual(committed);
 await page.reload();await expect(page.locator('#assessment-action-button')).toBeVisible();
 await start(page);
 const after=profileReceipts(stand);
 expect(after.profiles).toEqual(committed.profiles);expect(after.cycles).toHaveLength(1);
 expect(after.cycles[0].personalized_profile_id).toBe(after.profiles[0].id);
 expect(after.cycles[0].organization_id).toBe(after.profiles[0].organization_id);
 expect(after.cycles[0].owner_user_id).toBe(before.owner);
 expect(after.cycles[0].profile_ref_json.checksum).toBe(after.profiles[0].checksum);
 expect(after.cycles[0].situations).toBe(1);
 await info.attach('profile-cycle-receipts',{body:JSON.stringify({before,committed,after},null,2),contentType:'application/json'});
});
test('P10.5 ready profile with no admitted catalog',async({page,stand},info)=>{
 await login(page,stand,'participant@example.test',true);
 const ready=profileReceipts(stand);expect(ready.profiles[0].status).toBe('ready');
 await page.locator('#assessment-action-button').click();await page.locator('#prechat-start-button').click();
 await expect(page.locator('#prechat-error')).toContainText('Профиль готов');
 await expect(page.locator('#prechat-error')).toContainText('допустимые кейсы');
 expect(profileReceipts(stand)).toEqual(ready);
 await expect(page.getByRole('button',{name:'Подтвердить профиль',exact:true})).toBeHidden();
 await info.attach('ready-no-catalog',{body:await page.screenshot({fullPage:true}),contentType:'image/png'});
 await info.attach('no-empty-cycle',{body:JSON.stringify(ready,null,2),contentType:'application/json'});
});


// G10.7: independent integrated path, no legacy fixture or HTTP route replacement.
test('G10.7 fresh participant, immutable M4, logout history and independent Cycle',async({page,stand},info)=>{
 test.setTimeout(240000);
 const before=profileReceipts(stand);
 expect(before.user_context_count).toBe(0);expect(before.profiles).toEqual([]);expect(before.cycles).toEqual([]);
 expect(Object.values(before.output_counts).every(n=>n===0)).toBe(true);
 await info.attach('G01-empty-owner-inputs-and-all-outputs',{body:JSON.stringify(before,null,2),contentType:'application/json'});
 await login(page,stand,'participant@example.test',true);
 const ready=profileReceipts(stand);expect(ready.profiles).toHaveLength(1);
 await start(page);await answer(page);
 await page.locator('#interview-finish-button').click();
 await expect(page.locator('#interview-messages')).toContainText(fixture.question,{timeout:30000});
 await answer(page,fixture.clarification_answer);await page.locator('#interview-finish-button').click();
 const first=await report(page,stand,info);
 const resultUrl=`${stand.url}/users/assessment/m8/cycles/${first.cycle_id}/results`;
 const results=await (await page.request.get(resultUrl)).json();
 const after=profileReceipts(stand);
 expect(after.cycles[0].owner_user_id).toBe(before.owner);
 expect(after.cycles[0].personalized_profile_id).toBe(ready.profiles[0].id);
 expect(after.cycles[0].organization_id).toBe(ready.profiles[0].organization_id);
 expect(after.cycles[0].profile_ref_json.checksum).toBe(ready.profiles[0].checksum);
 expect(results.results.personalized_profile_snapshot.content.user_context.position_or_status).toBe('Эксперт по программам');
 const selection=first.c67.recommendation_generation.input.context_selection;
 expect(selection.status).toBe('available');expect(first.c67.recommendations.length).toBeGreaterThan(0);
 for(const rec of first.c67.recommendations){
   expect(rec.application_context).toContain(selection.value);
   await expect(page.locator('#report-panel')).toContainText(rec.application_context);
 }
 const projection=JSON.stringify(first.c67.recommendation_generation.input.profile_projection);
 expect(projection).not.toContain('participant@example.test');expect(projection).not.toContain('full_name');
 await page.locator('#report-back-button').click();
 await page.locator('#dashboard-panel .user-chip').click();await page.locator('#dashboard-restart-button').click();
 await expect(page.locator('#email-input')).toBeVisible();
 await page.context().clearCookies();await page.evaluate(()=>{localStorage.clear();sessionStorage.clear();});
 await login(page,stand);
 await expect(page.locator('.reports-summary-count')).toHaveText('1');
 await page.locator('.reports-summary-button').click();await expect(page.locator('.cycle-report')).toHaveCount(1);
 await page.locator('.cycle-report-open').click();await expect(page.locator('#m8-report-state')).toContainText('Report готов');
 expect(await (await page.request.get(`${stand.url}/users/assessment/m8/reports/${first.id}`)).json()).toEqual(first);
 expect(await (await page.request.get(resultUrl)).json()).toEqual(results);
 expect(profileReceipts(stand)).toEqual(after); // No hidden re-evaluation on login/read.
 const download=page.waitForEvent('download');await page.locator('#report-download-button').click();
 const pdf=path.join(stand.dir,'relogin.pdf');await (await download).saveAs(pdf);
 const checked=spawnSync(python,['scripts/verify_browser_pdf.py',pdf,path.join(stand.dir,'report.json')],{encoding:'utf8'});
 expect(checked.status,checked.stderr).toBe(0);
 await info.attach('G02-relogin-pdf',{path:pdf,contentType:'application/pdf'});
 await page.locator('#report-back-button').click();await page.locator('#reports-back-button').click();
 await start(page);await answer(page);await page.locator('#interview-finish-button').click();
 await expect(page.locator('#interview-messages')).toContainText(fixture.question,{timeout:30000});
 await answer(page,fixture.clarification_answer);await page.locator('#interview-finish-button').click();
 const secondDir=path.join(stand.dir,'G03-second');fs.mkdirSync(secondDir);
 const second=await report(page,{...stand,dir:secondDir},info);
 expect(second.cycle_id).not.toBe(first.cycle_id);expect(second.results_revision_id).not.toBe(first.results_revision_id);
 for(const rec of second.c67.recommendations)for(const basis of rec.basis_refs)expect(basis.cycle_id).toBe(second.cycle_id);
 const regenerateUrl=`${stand.url}/users/assessment/m8/cycles/${first.cycle_id}/reports/regenerate`;
 const regenerated=await page.request.post(regenerateUrl,{data:{idempotency_key:'G03-representation'}});
 expect(regenerated.status()).toBe(201);const revision=await regenerated.json();
 expect(revision.id).not.toBe(first.id);expect(revision.results_revision_id).toBe(first.results_revision_id);
 expect(await (await page.request.post(regenerateUrl,{data:{idempotency_key:'G03-representation'}})).json()).toEqual(revision);
 expect(await (await page.request.get(resultUrl)).json()).toEqual(results);
 expect(await (await page.request.get(`${stand.url}/users/assessment/m8/reports/${first.id}`)).json()).toEqual(first);
 await page.locator('#report-back-button').click();await page.locator('.reports-summary-button').click();
 await expect(page.locator('.cycle-report')).toHaveCount(2);
 await expect(page.locator(`.cycle-report[data-cycle-id="${first.cycle_id}"] option`)).toHaveCount(2);
 await info.attach('G03-two-independent-results',{body:await page.screenshot({fullPage:true}),contentType:'image/png'});
 await info.attach('G01-03-receipts',{body:JSON.stringify({before,ready,after,final:profileReceipts(stand),first,second,revision,results},null,2),contentType:'application/json'});
});
