import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import { pathToFileURL } from 'node:url';
const [id, root, out] = process.argv.slice(2);
const profile = await import(pathToFileURL(path.join(root, 'tests/browser/fixtures/assessment-completion-profile.mjs')));
const save = (value) => { fs.writeFileSync(path.join(out, id + '.json'), JSON.stringify(value, null, 2) + '\n'); console.log(JSON.stringify(value)); };
if (id === 'L02') {
  let phase = 'active', q = 0, replies = 0, turns = 0;
  const waiters = [];
  const response = (url) => ({ok: () => true, url: () => url,
    request: () => ({method: () => 'POST'})});
  const snapshot = () => ({cycle_id:'cycle-audit', status:{collection_status:'active'},
    current_situation:{assessment_situation_id:'as-audit',status:phase, participant_payload:{introduction:'synthetic'}},
    trace:{turns:Array.from({length:turns}, () => ({speaker_type:'assessee'}))},
    clarification:q ? {id:'q'+q,status:'ASK',question_turn_id:'q'+q,response_outcome:null} : null,
    finish_availability:{allowed:false}});
  const emit = (url) => { for (const item of [...waiters]) if(item.predicate(response(url))) {
    waiters.splice(waiters.indexOf(item),1); item.resolve(response(url)); } };
  const page = {on:()=>{}, request:{get:async () => ({ok:()=>true,json:async()=>snapshot()})},
    waitForResponse:predicate=>new Promise(resolve=>waiters.push({predicate,resolve})),
    waitForTimeout:ms=>new Promise(resolve=>setTimeout(resolve,Math.min(ms,1))),
    locator:selector=>({fill:async()=>{},waitFor:async()=>{},click:async()=>{
      if(selector==='#interview-submit-button') {
        turns++;
        if(phase==='active') emit('http://fixture.invalid/users/assessment/m5/situations/as-audit/turns');
        else {const old=q; q=q===1?2:1; replies++;
          fs.writeFileSync(path.join(out,'L02-counter.json'),JSON.stringify({accepted_ask_answers:replies,assessee_turns:turns,maxSituations:2,as_count:1,latest_ask:'q'+q}));
          emit('http://fixture.invalid/users/assessment/m7/clarifications/q'+old+'/answers');}
      } else if(selector==='#interview-finish-button') {
        phase='scenario_ended';q=1;
        emit('http://fixture.invalid/users/assessment/m5/situations/as-audit/transitions');
      }
    }})};
  // Yield in the external adapter only; no new stop condition in the driver.
  await profile.completeStartedAssessment({page,base:'http://fixture.invalid',cycleId:'cycle-audit',
    runId:'audit-L02',evidenceDir:out,initialSituationId:'as-audit',maxSituations:2,
    advanceWorkers:()=>new Promise(resolve=>setTimeout(resolve,1))});
  save({unexpected:'driver returned'}); process.exitCode=1;
} else if(id==='L03') {
  let callback; const test=(_name,fn)=>{callback=fn;}; test.setTimeout=()=>{}; test.info=()=>({annotations:[]});
  const source=fs.readFileSync(path.join(root,'tests/browser/path29-participant.spec.mjs'),'utf8').replace(/^import .*;\n/gm,'');
  const fakeProcess={cwd:()=>root,env:{STAND_ADMIN_URL:'synthetic-placeholder-no-connection',P4K_FULL_PATH:'1',
    P4K_REAL_PROVIDER:'1',P4K_CONTROLLED_PROVIDER:'1',P4K_PROGRAM_SOURCE:'published-pilot',P4K_EVIDENCE_DIRECTORY:path.join(out,'L03-fixture')}};
  vm.runInNewContext(source,{test,process:fakeProcess,path,fs,randomUUID:()=> 'audit-L03'});
  let reason; try { await callback({browser:{newContext:()=>{throw Error('AUDIT_BROWSER_MUST_NOT_START');}}}); }
  catch(e){reason=e.message;}
  save({status:reason==='CONTROLLED_PROVIDER_REQUIRES_PUBLISHED_OWNED_PATH'?'PARTIAL':'FAIL',reason,
    native_guard_rejected:true,scope:'actual PATH29 callback, conflicting real+controlled flags; missing adapter not executed'});
} else if(id==='L06-export') {
  const fixture={run_id:'audit-L06',cycle_id:'cycle-audit',collection_status:'active',situations:[],pipeline:{status:'processing'}};
  const page={request:{get:async()=>({ok:()=>true,json:async()=>fixture})}};
  const commands=[]; let exportError,cleanupError;
  const dir=path.join(out,'L06-run');fs.mkdirSync(dir,{recursive:true});
  try {await profile.readExecutionExport(page,'http://fixture.invalid','cycle-audit','audit-L06',dir,'readback');}
  catch(e){exportError=e.message;}
  try {profile.destroyOwnedStandIfAdmitted({executionStarted:true,terminalExecutionExportSaved:false,
    preparationReceiptRequired:true,terminalPreparationReceiptSaved:true,statePath:path.join(dir,'state-not-created.json'),
    runId:'audit-L06',save:()=>{},cli:action=>commands.push(action)});}
  catch(e){cleanupError=e.message;}
  fs.writeFileSync(path.join(dir,'run.json'),JSON.stringify({run_id:'audit-L06',database:'product4k_pytest_not_created',profile:'assessment-execution-contour/2'}));
  fs.writeFileSync(path.join(dir,'cleanup-deferred.json'),JSON.stringify({reason:'TERMINAL_EXECUTION_EXPORT_UNVERIFIED',database_preserved:true,fixture_only:true}));
  save({exportError,cleanupError,commands,diagnostic_file_retained:fs.existsSync(path.join(dir,'terminal-execution-export.json')),
    actual_database:'NOT_CREATED',scope:'existing export+cleanup functions; command spy is not DB readback'});
}
