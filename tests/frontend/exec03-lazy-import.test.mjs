import assert from 'node:assert/strict';
import fs from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';
import { createInterviewHarness } from './helpers/p3-a-interview.mjs';

// Production dispatch and delivery functions, isolated DOM/storage/HTTP. These
// regressions verify the state captured before lazy import, not real HTTP/PG.
const SOURCE = new URL('../../web/js/wiring.js', import.meta.url);
const LEGACY = 'agent4k.assessmentDraft:cycle-a:as-a';
const ASK1 = '00000000-0000-4000-8000-000000000098';
const ASK2 = '00000000-0000-4000-8000-000000000096';
const QUESTION = '00000000-0000-4000-8000-000000000097';
const json = (value) => new Response(JSON.stringify(value), { headers: { 'Content-Type': 'application/json' } });
const tick = async () => { for (let index = 0; index < 30; index += 1) await Promise.resolve(); };
const deferred = () => { let resolve; const promise = new Promise((yes) => { resolve = yes; }); return { promise, resolve }; };
const input = (h, value) => { h.textarea.value = value; h.textarea.listeners.get('input')(); };
const ask = (h, id) => {
  const runtime = h.snapshot();
  runtime.current_situation.status = 'scenario_ended';
  runtime.clarification = { id, status: 'ASK', question_turn_id: QUESTION, question: { text: 'Текущее уточнение' } };
  return runtime;
};
const setup = (clarificationId = null) => {
  const h = createInterviewHarness();
  h.subject.initInterview();
  h.runtime = clarificationId ? ask(h, clarificationId) : h.snapshot();
  h.subject.renderProductRuntime(h.runtime); h.flush();
  const loading = deferred();
  h.context.loadInterview = () => loading.promise;
  h.context.interviewSubmitLabel = { textContent: '' };
  const wiring = fs.readFileSync(SOURCE, 'utf8');
  vm.runInContext(wiring.slice(wiring.indexOf('let failedInterviewMessage ='),
    wiring.indexOf("interviewForm.addEventListener('submit'"))
    + '\nglobalThis.wiringSubject = {submitCurrentInterviewAnswer};', h.context);
  return { h, loading };
};
const saveTurn = (runtime, body) => {
  const turn = { turn_id: body.turn_id, request_id: body.request_id,
    speaker_type: 'assessee', content_text: body.content, sequence_no: 1 };
  runtime.trace.turns.push(turn); return turn;
};

test('EXEC-03 lazy-import acceptance cannot erase a newer draft revision even when raw text is identical', async () => {
  const { h, loading } = setup();
  const raw = '  Тот же самый собственный текст\nс сохранёнными пробелами  ';
  input(h, raw);
  const originalRevision = JSON.parse(h.storage.get(LEGACY + ':context')).revision;
  const sending = h.context.wiringSubject.submitCurrentInterviewAnswer();
  // A real input sequence replaces the draft after Submit while code loads.
  // The value happens to be equal; revision, not text equality, distinguishes it.
  input(h, ''); input(h, raw);
  const newRevision = JSON.parse(h.storage.get(LEGACY + ':context')).revision;
  assert.notEqual(newRevision, originalRevision);
  h.setFetch(async (_url, options) => {
    if (!options?.method) return json(h.runtime);
    const body = JSON.parse(options.body);
    assert.equal(body.content, raw.trim());
    return json({ turn: saveTurn(h.runtime, body) });
  });
  loading.resolve(h.subject); await sending; await tick();
  assert.equal(h.fetchCalls.filter(([, options]) => options?.method === 'POST').length, 1);
  assert.equal(h.runtime.trace.turns.length, 1);
  assert.equal(h.textarea.value, raw, 'accepted old send cannot clear a later revision with equal text');
  assert.equal(h.storage.get(LEGACY), raw);
  assert.equal(JSON.parse(h.storage.get(LEGACY + ':context')).revision, newRevision);
});

test('EXEC-03 lazy import cannot retarget a captured submission when the current question changes in the same AS', async () => {
  for (const sourceQuestion of [null, ASK1]) {
    const { h, loading } = setup(sourceQuestion);
    const oldRaw = sourceQuestion ? 'Ответ на прежнее уточнение' : 'Ответ на основной сценарий';
    input(h, oldRaw);
    const sending = h.context.wiringSubject.submitCurrentInterviewAnswer();
    h.runtime = ask(h, ASK2);
    h.subject.renderProductRuntime(h.runtime);
    input(h, 'Новый собственный draft для текущего вопроса');
    h.setFetch(async (_url, options) => {
      if (!options?.method) return json(h.runtime);
      const body = JSON.parse(options.body); saveTurn(h.runtime, body);
      return json({ id: ASK2, answer_turn_id: body.turn_id,
        response_request_id: body.request_id, response_outcome: 'answered' });
    });
    loading.resolve(h.subject); await sending; await tick();
    assert.equal(h.fetchCalls.length, 0, 'stale captured question exits before any new request');
    assert.equal(h.runtime.trace.turns.length, 0);
    assert.equal(h.textarea.value, 'Новый собственный draft для текущего вопроса');
    assert.equal(h.storage.get(LEGACY + ':8:' + ASK2), 'Новый собственный draft для текущего вопроса');
    assert.equal(h.subject.readProductInterviewAnswer(), null, 'old submission creates no identity for the new question');
  }
});

test('EXEC-03 legacy pending operation gains a revision before readback so equal newer input survives', async () => {
  const { h } = setup();
  const raw = '  Legacy pending answer\nс идентичным новым вводом  ';
  input(h, raw);
  const original = h.subject.prepareProductInterviewAnswer(raw.trim(), raw);
  const pendingKey = 'agent4k.assessmentPending:cycle-a:as-a:8';
  const legacyOperation = JSON.parse(h.storage.get(pendingKey));
  legacyOperation.status = 'unknown';
  delete legacyOperation.draftRevision;
  h.storage.set(pendingKey, JSON.stringify(legacyOperation));
  const reading = deferred();
  h.setFetch(async (url) => String(url).includes('/answer-status?') ? reading.promise : json(h.runtime));
  h.subject.renderProductRuntime(h.runtime);
  await tick();
  input(h, ''); input(h, raw);
  const newerRevision = JSON.parse(h.storage.get(LEGACY + ':context')).revision;
  reading.resolve(json({ status: 'accepted', processing_status: 'applied',
    cycle_id: original.cycleId, assessment_situation_id: original.situationId,
    request_id: original.requestId, turn_id: original.turnId, clarification_id: null,
    turn: { turn_id: original.turnId, request_id: original.requestId,
      content_text: original.text, speaker_type: 'assessee' } }));
  await tick();
  assert.equal(h.subject.readProductInterviewAnswer(), null);
  assert.equal(h.textarea.value, raw, 'legacy operation acceptance cannot clear a newer revision with equal raw text');
  assert.equal(h.storage.get(LEGACY), raw);
  assert.equal(JSON.parse(h.storage.get(LEGACY + ':context')).revision, newerRevision);
  assert.equal(h.fetchCalls.filter(([, options]) => options?.method === 'POST').length, 0);
});
