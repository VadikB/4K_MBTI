import assert from 'node:assert/strict';
import test from 'node:test';
import vm from 'node:vm';
import { createInterviewHarness } from './helpers/p3-a-interview.mjs';

const key = 'agent4k.assessmentPending:cycle-a:as-a:8';
const json = (value) => new Response(JSON.stringify(value), { headers: { 'Content-Type': 'application/json' } });
const tick = async () => { for (let n = 0; n < 40; n += 1) await Promise.resolve(); };
const prepare = () => {
  const h = createInterviewHarness(); h.subject.initInterview();
  h.subject.renderProductRuntime(h.snapshot()); h.flush();
  h.textarea.value = 'Исходный ответ'; h.textarea.listeners.get('input')();
  const operation = h.subject.prepareProductInterviewAnswer('Исходный ответ', h.textarea.value);
  h.storage.set(key, JSON.stringify({ ...operation, status: 'unknown' }));
  // Real Storage exposes its stored keys as enumerable own properties. The
  // small existing harness keeps values in Map, so model that surface here.
  Object.defineProperty(h.context.window.sessionStorage, key, { enumerable: true, get: () => h.storage.get(key) });
  vm.runInContext('globalThis.subject.recoverCompletedInterviewAnswers = recoverCompletedInterviewAnswers;', h.context);
  return { h, operation };
};
const accepted = (operation) => ({ cycle_id: operation.cycleId, assessment_situation_id: operation.situationId,
  request_id: operation.requestId, turn_id: operation.turnId, clarification_id: null,
  status: 'accepted', processing_status: 'applied', turn: { request_id: operation.requestId,
    turn_id: operation.turnId, content_text: operation.text, speaker_type: 'assessee' } });

for (const terminal of [false, true]) {
  test(`EXEC03 unknown previous AS resolves without transferring its text into ${terminal ? 'processing' : 'next AS'}`, async () => {
    const { h, operation } = prepare();
    let resolve; const held = new Promise((yes) => { resolve = yes; });
    h.setFetch(async (url) => { assert.ok(url.includes('/as-a/answer-status?')); return held; });
    if (terminal) {
      h.state.currentScreen = 'processing'; h.state.productAssessmentSituationId = null;
      h.subject.recoverCompletedInterviewAnswers('cycle-a');
    } else {
      h.subject.renderProductRuntime(h.snapshot(0, 'as-b'));
      h.textarea.value = 'Новый собственный ввод'; h.textarea.listeners.get('input')();
    }
    resolve(json(accepted(operation))); await tick();
    assert.equal(h.storage.has(key), false);
    assert.equal(h.storage.has('agent4k.assessmentDraft:cycle-a:as-a'), false);
    if (!terminal) assert.equal(h.textarea.value, 'Новый собственный ввод');
    assert.equal(h.fetchCalls.filter(([, options]) => options?.method === 'POST').length, 0);
  });
}

test('EXEC03 late previous-AS recovery cannot clear a different login session', async () => {
  const { h, operation } = prepare();
  let resolve; h.setFetch(() => new Promise((yes) => { resolve = yes; }));
  h.state.currentScreen = 'processing'; h.state.productAssessmentSituationId = null;
  h.subject.recoverCompletedInterviewAnswers('cycle-a');
  h.state.identityEpoch += 1; h.state.pendingUser = { id: 9 };
  resolve(json(accepted(operation))); await tick();
  assert.equal(h.storage.has(key), true);
  assert.equal(h.storage.get('agent4k.assessmentDraft:cycle-a:as-a'), 'Исходный ответ');
});

for (const status of ['absent', 'pending', 'failed']) {
  test(`EXEC03 processing navigation retains ${status} identity without server source-phase proof`, async () => {
    const { h, operation } = prepare();
    const value = accepted(operation);
    value.status = status === 'absent' ? 'absent' : 'accepted';
    value.processing_status = status === 'absent' ? null : status;
    if (status === 'absent') value.turn = null;
    h.setFetch(async () => json(value));
    h.state.currentScreen = 'processing';
    h.subject.recoverCompletedInterviewAnswers('cycle-a'); await tick();
    assert.equal(JSON.parse(h.storage.get(key)).requestId, operation.requestId);
    assert.equal(JSON.parse(h.storage.get(key)).turnId, operation.turnId);
    assert.equal(h.storage.get('agent4k.assessmentDraft:cycle-a:as-a'), operation.draftValue);
    assert.equal(h.fetchCalls.filter(([, options]) => options?.method === 'POST').length, 0);
  });
}
