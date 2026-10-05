import { test as base, expect, chromium } from '@playwright/test';
import { spawn, spawnSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { randomUUID } from 'node:crypto';
const root=process.cwd(), python=process.env.BROWSER_PYTHON || path.join(root,'.venv/bin/python');
const fixture=JSON.parse(fs.readFileSync('tests/browser/fixtures/v1.json','utf8'));
const test=base.extend({context:async({browser},use,info)=>{
 if(info.title.includes('C1')){
   // Real background visibility: default Playwright focus emulation keeps every page visible.
   const owned=await chromium.launch({headless:false,
     ignoreDefaultArgs:['--disable-backgrounding-occluded-windows','--disable-renderer-backgrounding','--disable-background-timer-throttling'],
     args:['--remote-debugging-port=18831']});
   let connected;
   try{
     connected=await chromium.connectOverCDP('http://127.0.0.1:18831',{noDefaults:true});
     const context=connected.contexts()[0];
     context.restoreDownloadDefaults=async()=>{
       await connected.close();
       connected=await chromium.connectOverCDP('http://127.0.0.1:18831');
       return connected.contexts()[0];
     };
     await use(context);
   }
   finally{if(connected)await connected.close();await owned.close();}
 }else{
   const context=await browser.newContext({viewport:{width:1440,height:1000},locale:'ru-RU',acceptDownloads:true});
   try{await use(context);}finally{await context.close();}
 }
},stand:async({},use,info)=>{
  if(!process.env.STAND_ADMIN_URL) throw new Error('Explicit isolated STAND_ADMIN_URL required');
  const dir=path.join(root,'.test-stand/browser',randomUUID());fs.mkdirSync(dir,{recursive:true});
  const statePath=path.join(dir,'state.json'),port=18830;
  const cli=(action)=>{const r=spawnSync(python,['scripts/test_stand.py',action,'--state',statePath,'--port',String(port),'--gateway','1'],{encoding:'utf8'});fs.appendFileSync(path.join(dir,'prepare.log'),r.stdout+r.stderr);if(r.status!==0)throw new Error(action+': '+r.stderr);};
  let server;
  cli('create');
  try{
    cli('bootstrap');
    if(info.title.includes('character')){const inputs=JSON.parse(fs.readFileSync(statePath));inputs.browser_case='character';fs.writeFileSync(statePath,JSON.stringify(inputs));}
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
async function login(page,stand,email='participant@example.test'){
 page.on('dialog',dialog=>dialog.accept());
 page.on('response',async response=>{try{if(response.url().endsWith('/runtime') && response.ok()){page.acceptanceCycle=(await response.json()).cycle_id;}}catch{/* Navigation may discard diagnostic response bodies. */}});
 await page.goto(stand.url);
 await page.locator('#email-input').fill(email);
 await page.locator('#request-magic-link-button').click();
 await page.locator('#magic-token-input').fill(stand.state.password);
 await page.locator('#verify-magic-link-button').click();
 const confirm=page.getByRole('button',{name:'Подтвердить профиль',exact:true});
 await expect(confirm).toBeVisible();await confirm.click();
 await expect(page.locator('#assessment-action-button')).toBeVisible();
}
async function start(page,expected='готовности'){
 await page.locator('#assessment-action-button').click();
 await page.locator('#prechat-start-button').click();
 await expect(page.locator('#interview-textarea')).toBeEnabled({timeout:15000});
 await expect(page.locator('#interview-messages')).toContainText(expected);
 await test.info().attach('interview-start',{body:await page.screenshot({fullPage:true}),contentType:'image/png'});
}
async function answer(page,text=fixture.answer){await page.locator('#interview-textarea').fill(text);await page.locator('#interview-submit-button').click();await expect(page.locator('#interview-submit-button')).toBeEnabled({timeout:30000});await expect(page.locator('#interview-error')).toBeHidden();await expect(page.locator('#interview-messages .own')).toContainText([text]);}
async function report(page,stand,info){
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
 await login(page,stand);await start(page);await answer(page);
 const before=await runtime(page,stand);
 await info.attach('runtime-before-expiry',{body:JSON.stringify(before,null,2),contentType:'application/json'});
 if(variant==='C2'){
   await page.locator('#interview-pause-button').click();await expect(page.locator('#interview-pause-button')).toHaveText('Продолжить');
   await page.close();page=await context.newPage();
 }else{
   const other=await context.newPage();await other.goto('about:blank');await other.bringToFront();
   await expect.poll(()=>page.evaluate(()=>document.visibilityState)).toBe('hidden');
   await info.attach('background-visibility',{body:JSON.stringify({at:new Date().toISOString(),visibility:await page.evaluate(()=>document.visibilityState)}),contentType:'application/json'});
 }
 const statusUrl=`${stand.url}/users/assessment/m7/cycles/${before.cycle_id}`;
 await expect.poll(async()=>{const r=await context.request.get(statusUrl);return (await r.json()).collection_status;},{timeout:60000,intervals:[500,1000]}).toBe('calculated');
 await info.attach('runtime-after-expiry',{body:JSON.stringify(await (await context.request.get(statusUrl)).json(),null,2),contentType:'application/json'});
 const late=await context.request.post(`${stand.url}/users/assessment/m5/situations/${before.current_situation.assessment_situation_id}/turns`,{data:{request_id:'late',turn_id:randomUUID(),content:'Late synthetic answer'}});expect(late.status()).toBe(409);
 await info.attach('late-turn',{body:JSON.stringify({status:late.status(),response:await late.json()}),contentType:'application/json'});
 if(variant==='C1'){
   // Same browser/tab/cookies. Restore ordinary download handling only after expiry proof.
   const restored=await context.restoreDownloadDefaults();
   page=restored.pages().find(p=>p.url().startsWith(stand.url));expect(page).toBeTruthy();
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
