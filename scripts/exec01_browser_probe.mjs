import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';

// Synthetic browser component probe. Production functions execute in Chromium;
// transport is a localhost fixture, not PostgreSQL / full application acceptance.
// Backend HTTP/PG evidence is required independently for A/B/C admission rules.
const root=process.env.EXEC01_ROOT || process.cwd();
const evidence=process.env.EXEC01_BROWSER_EVIDENCE || path.join(root,'.test-stand/exec01-browser');
fs.mkdirSync(evidence,{recursive:true});
const {chromium}=await import(pathToFileURL(path.join(root,'node_modules/playwright/index.mjs')).href);
const src=fs.readFileSync(path.join(root,'web/js/screens/interview.js'),'utf8');
const section=(a,b)=>src.slice(src.indexOf(a),src.indexOf(b)).replaceAll('export const ','const ');
const names=['interviewPanel','interviewMessages','interviewScrollArea','interviewMessagesScroll',
'interviewSummary','interviewCompleteActions','interviewCaseBadge','interviewProgressFill',
'interviewCaseTitle','interviewCaseStatus','interviewTimerBadge','interviewTitleRow',
'interviewCaseHeading','interviewTextarea','interviewSubmitButton','interviewFinishButton',
'interviewPauseButton','interviewAdditionalButton','interviewError','caseProgressList',
'interviewRouteLabel','caseSidebar','caseSidebarToggle','caseSidebarToggleLabel','prechatError'];
const wrapper=`
const state={currentScreen:'interview',productCycleId:'00000000-0000-4000-8000-000000000001',
 productAssessmentSituationId:'00000000-0000-4000-8000-000000000002',pendingUser:{id:8},
 identityEpoch:1,assessmentRuntimeKind:'cycle'};
const safeStorage=sessionStorage,STORAGE_KEYS={completionPending:'fixture-completion'};
const createOperationId=()=>crypto.randomUUID();
const readApiResponse=async(response,message)=>{const body=await response.json();if(!response.ok)throw new Error(body.detail||message);return body;};
const showError=(element,message)=>element.textContent=message;
const persistAssessmentContext=()=>{},renderInterviewMeta=()=>{},renderCaseProgress=()=>{},
 updateInterviewTimer=()=>{},updateInterviewMessagesScrollIndicator=()=>{},
 cancelInterviewScrollAlignment=()=>{},scheduleInterviewScrollAlignment=()=>{},
 scheduleInterviewBottomAlignment=()=>{},isInterviewNearBottom=()=>true,
 parseInterviewAssistantMessage=()=>null,resumeProductRuntimePolling=()=>{},
 openProcessing=()=>{state.currentScreen='processing';};
${names.map(name=>`const ${name}=document.getElementById('${name}');`).join('\n')}
const interviewCompactQuery=null;
let productRuntimePollGeneration=0,returnHeartbeatTimer=null,returnPresenceCycleId=null,
 returnPresenceGeneration=0,activeInterviewDraftKey=null,renderedProductMessages=null,
 renderedProductCycleId=null,confirmedProductInterviewSnapshot=null,confirmedProductInterviewCanSend=false;
const RETURN_CONTINUE_PENDING_KEY='agent4k.returnContinuePending',PRODUCT_RUNTIME_POLL_MS=20,
 returnClientId=crypto.randomUUID(),productInterviewRequests=new Map();
${section('const interviewDraftKey =','\nconst payloadText =')}
${section('const payloadText =','\nconst renderProductRuntime =')}
${section('const renderProductRuntime =','\nexport const toggleProductPause =')}
${section('const renderInterviewStructuredBlock =','\nexport const addInterviewMessage =')}
${section('export const addInterviewMessage =','\nconst isInterviewNearBottom =')}
window.subject={renderProductRuntime,renderReturnCard,loadProductRuntime,finishProductAssessment,stopProductPresence,state};
document.getElementById('interviewFinishButton').addEventListener('click',()=>{window.finishPromise=finishProductAssessment().catch(error=>showError(interviewError,error.message));});
window.ready=true;
`;
const html=`<!doctype html><html lang="ru"><meta charset="utf-8"><style>
body{font:16px sans-serif;margin:20px}#interviewMessages{border:1px solid #ccc;padding:12px}
button,textarea{margin:8px;padding:10px}#interviewCaseStatus{color:#333}.hidden{display:none}
</style><body><p>Synthetic EXEC01 browser component fixture</p>${names.map(name=>{
const tag=name==='interviewTextarea'?'textarea':name.endsWith('Button')?'button':'div';
return '<'+tag+' id="'+name+'">'+(name.endsWith('Button')?name:'')+'</'+tag+'>';
}).join('\n')}<script type="module" src="/subject.mjs"></script></body></html>`;
const cycle='00000000-0000-4000-8000-000000000001';
const as='00000000-0000-4000-8000-000000000002';
const decision='00000000-0000-4000-8000-000000000003';
const baseModel={cycle_id:cycle,current_situation:{assessment_situation_id:as,status:'scenario_ended',
 participant_payload:{title:'Синтетическая сохранённая AS',introduction:'Синтетический текст ситуации'}},
 route:{positions:[]},status:{collection_status:'active',remaining_seconds:4800},
 trace:{turns:[{turn_id:'00000000-0000-4000-8000-000000000004',sequence_no:1,speaker_type:'assessee',content_text:'Сохранённый ответ'}],events:[]},
 return_policy_enabled:true,finish_availability:{allowed:false,reason:'INTERIM_PENDING'}};
const askModel={...baseModel,clarification:{id:decision,status:'ASK',question:{text:'Синтетический уточняющий вопрос'},question_turn_id:'00000000-0000-4000-8000-000000000005'},finish_availability:{allowed:false,reason:'OPEN_ASK'}};
const returnCard={cycle_id:cycle,collection_status:'interrupted',allowed_action:'continue_current',
 position_no:1,current_assessment_situation_id:as,current_assessment_situation_status:'scenario_ended',
 progress:{completed_positions:0,total_positions:2},remaining_seconds:4800};
let model=structuredClone(baseModel),returned=true,presenceFailures=0,presenceConflicts=0;
const requests=[];
const server=http.createServer(async(req,res)=>{
 if(req.url==='/'){res.setHeader('Content-Type','text/html');return res.end(html);}
 if(req.url==='/subject.mjs'){res.setHeader('Content-Type','text/javascript');return res.end(wrapper);}
 let text='';for await(const chunk of req)text+=chunk;
 let body=null;try{body=text?JSON.parse(text):null;}catch{}
 requests.push({method:req.method,path:req.url,body});
 res.setHeader('Content-Type','application/json');
 const json=value=>res.end(JSON.stringify(value));
 if(req.url.endsWith('/return-state')) return json(returned?{cycle_id:cycle,allowed_action:'none'}:returnCard);
 if(req.url.endsWith('/return-continue')) {returned=true;return json({assessment_situation_id:as,branch:'continued_current'});}
 if(req.url.endsWith('/runtime')) return json(model);
 if(req.url.endsWith('/presence')){
  if(presenceConflicts-->0){res.statusCode=409;return json({detail:'Synthetic recognized absence'});}
  if(presenceFailures-->0){res.statusCode=503;return json({detail:'Synthetic transient presence error'});}
  return json({heartbeat_interval_seconds:.05});
 }
 if(req.url.endsWith('/next')) {model={...structuredClone(askModel),current_situation:{...askModel.current_situation,assessment_situation_id:'00000000-0000-4000-8000-000000000006'}};return json({decision:{status:'SELECTED'}});}
 if(req.url.endsWith('/finish-situation')) return json({status:'completed'});
 res.statusCode=404;json({detail:'Synthetic route not found'});
});
await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
const base='http://127.0.0.1:'+server.address().port;
const browser=await chromium.launch({headless:true});
const results={source_interview_sha256:createHash('sha256').update(src).digest('hex'),scope:'synthetic component only; real Chromium DOM and actual localhost HTTP; no PostgreSQL or full app authentication',checks:[]};
async function check(name,callback){try{await callback();results.checks.push({name,status:'PASS'});}catch(error){results.checks.push({name,status:'FAIL',error:error.message});}}
async function newPage(){const page=await browser.newPage({viewport:{width:390,height:844}});await page.goto(base);await page.waitForFunction(()=>window.ready);return page;}
try{
 await check('C1/C3 pending/error/stale server state disables Finish with visible status',async()=>{
  const page=await newPage();
  try{for(const reason of ['INTERIM_PENDING','WAIT_TECHNICAL','DECISION_STALE','ANALYSIS_FAILED']){
   await page.evaluate(value=>window.subject.renderProductRuntime(value),{...baseModel,finish_availability:{allowed:false,reason}});
   const disabled=await page.locator('#interviewFinishButton').isDisabled();
   const status=await page.locator('#interviewCaseStatus').textContent();
   await page.screenshot({path:path.join(evidence,reason+'.png')});
   assert.equal(disabled,true,reason+' disabled');assert.ok(status.length>0,reason+' has visible status');
  }}finally{await page.close();}
 });
 await check('C3 current decision enables Finish; new accepted material pending blocks it again',async()=>{
  const page=await newPage();try{
   await page.evaluate(value=>window.subject.renderProductRuntime(value),{...baseModel,finish_availability:{allowed:true,reason:'CURRENT_DECISION'}});
   assert.equal(await page.locator('#interviewFinishButton').isDisabled(),false);
   await page.evaluate(value=>window.subject.renderProductRuntime(value),{...baseModel,finish_availability:{allowed:false,reason:'INTERIM_PENDING'}});
   assert.equal(await page.locator('#interviewFinishButton').isDisabled(),true);
  }finally{await page.close();}
 });
 await check('A1 ASK remains rendered after transient initial presence error',async()=>{
  const page=await newPage();try{model=structuredClone(askModel);presenceFailures=1;
   await page.evaluate(()=>window.subject.loadProductRuntime().catch(()=>{}));
   assert.equal(await page.locator('.interview-message--situation').count(),1);
   assert.equal(await page.locator('#interviewTextarea').isDisabled(),false);
   assert.ok((await page.locator('#interviewMessages').textContent()).includes('Синтетический уточняющий вопрос'));
   await page.screenshot({path:path.join(evidence,'ask-transient-presence.png')});
  }finally{await page.close();}
 });
 await check('A2 actual browser Continue request sends scenario_ended, reuses AS and draft, never generates replacement',async()=>{
  const page=await newPage();try{model=structuredClone(askModel);returned=false;presenceFailures=0;
   await page.evaluate(({cycle,as,value})=>{sessionStorage.setItem('agent4k.assessmentDraft:'+cycle+':'+as,'Синтетический черновик');window.subject.renderReturnCard(value);},{cycle,as,value:returnCard});
   const before=requests.length;
   await page.getByRole('button',{name:'Продолжить',exact:true}).click();
   await page.waitForFunction(()=>document.getElementById('interviewMessages').textContent.includes('Синтетический уточняющий вопрос'));
   const continued=requests.slice(before).filter(row=>row.path.endsWith('/return-continue'));
   assert.equal(continued.length,1);assert.equal(continued[0].body.expected_state,'scenario_ended');
   assert.equal(continued[0].body.expected_assessment_situation_id,as);
   assert.equal(continued[0].body.generation_operation_id,null);
   assert.equal(requests.slice(before).some(row=>row.path.endsWith('/equivalent-candidate')),false);
   assert.equal(await page.locator('#interviewTextarea').inputValue(),'Синтетический черновик');
   assert.equal(await page.evaluate(()=>window.subject.state.productAssessmentSituationId),as);
   await page.screenshot({path:path.join(evidence,'continue-same-as.png')});
  }finally{await page.close();}
 });

 await check('A1/A2 heartbeat loop resumes after recognized return and explicit Continue',async()=>{
  const page=await newPage();try{model=structuredClone(askModel);returned=true;presenceFailures=0;presenceConflicts=0;
   await page.evaluate(()=>window.subject.loadProductRuntime());
   returned=false;presenceConflicts=1;
   await page.getByRole('button',{name:'Продолжить',exact:true}).waitFor();
   const before=requests.filter(row=>row.path.endsWith('/presence')).length;
   await page.getByRole('button',{name:'Продолжить',exact:true}).click();
   await page.waitForFunction(()=>document.getElementById('interviewMessages').textContent.includes('Синтетический уточняющий вопрос'));
   await page.waitForTimeout(350);
   const after=requests.filter(row=>row.path.endsWith('/presence')).length;
   assert.ok(after-before>=3,'At least three presence POSTs after Continue, got '+(after-before));
  }finally{await page.close();}
 });

 await check('C6/A1 next situation in the same Cycle starts a fresh presence loop only after explicit Next',async()=>{
  const page=await newPage();try{model=structuredClone(askModel);returned=true;presenceFailures=0;presenceConflicts=0;
   await page.evaluate(()=>window.subject.loadProductRuntime());
   model={...structuredClone(baseModel),current_situation:null,between_situations:true,
    status:{collection_status:'paused',remaining_seconds:4800}};
   await page.evaluate(()=>window.subject.loadProductRuntime());
   await page.getByRole('button',{name:'Приступить к следующей ситуации',exact:true}).waitFor();
   await page.waitForTimeout(150);
   const before=requests.filter(row=>row.path.endsWith('/presence')).length;
   const nextBefore=requests.filter(row=>row.path.endsWith('/next')).length;
   assert.equal(nextBefore,0,'No automatic Next command');
   await page.getByRole('button',{name:'Приступить к следующей ситуации',exact:true}).click();
   await page.waitForFunction(()=>window.subject.state.productAssessmentSituationId==='00000000-0000-4000-8000-000000000006');
   await page.waitForTimeout(350);
   const after=requests.filter(row=>row.path.endsWith('/presence')).length;
   assert.ok(after-before>=3,'At least three fresh presence POSTs after Next, got '+(after-before));
  }finally{await page.close();}
 });
}finally{
 results.requests=requests;fs.writeFileSync(path.join(evidence,'results.json'),JSON.stringify(results,null,2)+'\n');
 await browser.close();await new Promise(resolve=>server.close(resolve));
}
console.log(JSON.stringify({scope:results.scope,checks:results.checks,evidence},null,2));
if(results.checks.some(row=>row.status==='FAIL'))process.exitCode=1;
