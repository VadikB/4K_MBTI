import test from 'node:test';
import assert from 'node:assert/strict';
import {createInterviewHarness} from './helpers/exec01-lifecycle-harness.mjs';

const response = (body, status=200) => ({ok:status >= 200 && status < 300, status, json:async()=>body});
const ended = (h, reason, allowed=false) => ({...h.snapshot(2),
  current_situation: {...h.snapshot().current_situation, status:'scenario_ended'},
  finish_availability:{allowed,reason}, return_policy_enabled:true});

for (const reason of ['INTERIM_PENDING','WAIT_TECHNICAL','DECISION_STALE','ANALYSIS_FAILED']) {
  test(`EXEC01 C1/C3 ordinary finish remains disabled for server ${reason}`, () => {
    const h=createInterviewHarness();
    const model=ended(h,reason);
    h.subject.renderProductRuntime(model);
    assert.equal(h.controls.finish.disabled,true);
    assert.equal(h.controls.submit.disabled,true);
    assert.equal(h.controls.textarea.disabled,true);
    assert.ok(h.context.interviewCaseStatus.textContent?.length > 0);
  });
}

test('EXEC01 C1 open ASK remains answerable and blocks Finish', () => {
  const h=createInterviewHarness();
  const model=ended(h,'OPEN_ASK');
  model.clarification={id:'00000000-0000-4000-8000-000000000003',status:'ASK',
    question:{text:'Синтетическое уточнение'}, question_turn_id:'question-1'};
  h.subject.renderProductRuntime(model);
  assert.equal(h.controls.finish.disabled,true);
  assert.equal(h.controls.submit.disabled,false);
  assert.equal(h.controls.textarea.disabled,false);
});

test('EXEC01 C2 server current decision enables ordinary Finish; new pending snapshot locks it again', () => {
  const h=createInterviewHarness();
  h.subject.renderProductRuntime(ended(h,'CURRENT_DECISION',true));
  assert.equal(h.controls.finish.disabled,false);
  h.subject.renderProductRuntime(ended(h,'INTERIM_PENDING'));
  assert.equal(h.controls.finish.disabled,true);
});

test('EXEC01 A1 failed first presence never hides the already confirmed ASK/history', async () => {
  const h=createInterviewHarness();
  h.state.productAssessmentSituationId='as-a';
  const model=ended(h,'OPEN_ASK');
  model.clarification={id:'00000000-0000-4000-8000-000000000003',status:'ASK',
    question:{text:'Синтетическое уточнение'}, question_turn_id:'question-1'};
  h.setFetch(async(url)=>{
    if(url.endsWith('/return-state')) return response({cycle_id:'cycle-a',allowed_action:'none'});
    if(url.endsWith('/runtime')) return response(model);
    if(url.endsWith('/presence')) throw new Error('Synthetic transient presence failure');
    throw new Error('Unexpected fetch: '+url);
  });
  await h.subject.loadProductRuntime().catch(()=>{});
  assert.equal(h.messages.children.some(row=>row.className.includes('interview-message--situation')),true);
  assert.equal(h.controls.textarea.disabled,false);
  assert.equal(h.controls.finish.disabled,true);
});

test('EXEC01 A2 Continue preserves the AS and ordinary draft without retargeting it into ASK', async () => {
  const h=createInterviewHarness();
  const value={cycle_id:'cycle-a',collection_status:'interrupted',allowed_action:'continue_current',
    position_no:1,current_assessment_situation_id:'as-a',current_assessment_situation_status:'scenario_ended',
    progress:{completed_positions:0,total_positions:2},remaining_seconds:4800};
  const model=ended(h,'OPEN_ASK');
  model.clarification={id:'00000000-0000-4000-8000-000000000003',status:'ASK',
    question:{text:'Синтетическое уточнение'}, question_turn_id:'question-1'};
  let continued=false;
  h.setFetch(async(url,options)=>{
    if(url.endsWith('/return-continue')) {continued=true; return response({assessment_situation_id:'as-a',branch:'continued_current'});}
    if(url.endsWith('/presence')) return response({heartbeat_interval_seconds:20});
    if(url.endsWith('/return-state')) return response({cycle_id:'cycle-a',allowed_action:continued?'none':'continue_current'});
    if(url.endsWith('/runtime')) return response(model);
    throw new Error('Unexpected fetch: '+url);
  });
  h.storage.set('agent4k.assessmentDraft:cycle-a:as-a','Синтетический черновик');
  h.subject.renderReturnCard(value);
  const button=h.messages.firstChild.children.find(child=>child.textContent==='Продолжить');
  await button.listeners.get('click')();
  const calls=h.fetchCalls.filter(([url])=>url.endsWith('/return-continue'));
  assert.equal(calls.length,1);
  const body=JSON.parse(calls[0][1].body);
  assert.equal(body.expected_state,'scenario_ended');
  assert.equal(body.expected_assessment_situation_id,'as-a');
  assert.equal(body.position_no,1);
  assert.equal(body.generation_operation_id,null);
  assert.equal(h.fetchCalls.some(([url])=>url.endsWith('/equivalent-candidate')),false);
  assert.equal(h.state.productAssessmentSituationId,'as-a');
  assert.equal(h.storage.get('agent4k.assessmentDraft:cycle-a:as-a'),'Синтетический черновик');
  assert.equal(h.textarea.value,'');
});
