import assert from 'node:assert/strict';
import fs from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';
import { createInterviewHarness } from './helpers/p3-a-interview.mjs';

const json = value => new Response(JSON.stringify(value));
const tick = async () => { for (let i = 0; i < 30; i++) await Promise.resolve(); };
const setup = () => {
  const h = createInterviewHarness(); h.runtime = h.snapshot(20);
  h.subject.renderProductRuntime(h.runtime); h.flush(); return h;
};
const waiting = h => {
  const s = h.snapshot(20); s.current_situation.status = 'scenario_ended';
  s.trace.turns.push({ turn_id: 'last-answer', request_id: 'last-request', sequence_no: 21,
    speaker_type: 'assessee', content_text: 'Сохранённый ответ' });
  s.blocking_system_wait = true; s.finish_availability = { allowed: false, reason: 'ANALYSIS_PENDING' };
  s.pipeline = { status: 'running' }; return s;
};
const notice = h => h.context.interviewError.textContent;

test('C1 own pending row follows the new bottom after insertion; layout callbacks respect manual scroll', async () => {
  const h = setup(); h.area.scrollTop = 400; h.textarea.value = 'Новый ответ';
  let release; h.setFetch(() => new Promise(resolve => { release = resolve; }));
  const sending = h.subject.sendProductInterviewAnswer(h.textarea.value); await tick(); h.flush();
  assert.ok(h.messages.children.some(row => row.dataset.pendingTurnId));
  assert.equal(h.area.scrollTop, h.area.scrollHeight - h.area.clientHeight);
  h.area.scrollTop = 222; h.flush(); assert.equal(h.area.scrollTop, 222);
  h.setFetch(() => json(h.runtime));
  release(json(h.runtime)); await sending;
});

test('C2 background trace update preserves reading position and the exact draft', () => {
  const h = setup(); h.area.scrollTop = 330; h.textarea.value = 'Черновик\nс продолжением';
  h.storage.set('agent4k.assessmentDraft:cycle-a:as-a', h.textarea.value);
  h.subject.renderProductRuntime(h.snapshot(22)); h.flush();
  assert.equal(h.area.scrollTop, 330); assert.equal(h.button.hidden, false);
  assert.equal(h.textarea.value, 'Черновик\nс продолжением');
});

test('C3/C6 current receipt is above composer; fresh/delayed/failed/read failure use server facts', () => {
  const h = setup(), s = waiting(h); h.subject.renderProductRuntime(s);
  assert.match(notice(h), /Ответ сохранён\. Идёт обработка/);
  assert.match(notice(h), /Время на ответы сейчас не расходуется/);
  assert.equal(h.context.interviewSubmitLabel.textContent, 'Отправить');
  // Existing wait budget; elapsed time alone never declares a failed pipeline.
  const key = [...h.storage.keys()].find(key => key.startsWith('agent4k.assessmentCommand:wait:'));
  const delayed = createInterviewHarness({ storage: new Map([[key, '1']]) });
  delayed.subject.renderProductRuntime(s); assert.match(notice(delayed), /Обработка занимает больше времени/);
  assert.doesNotMatch(notice(delayed), /завис|завершилась ошибкой/);
  s.pipeline.status = 'failed'; h.subject.renderProductRuntime(s);
  assert.match(notice(h), /Произошла ошибка обработки\. Подробности пока недоступны/);
  s.pipeline.status = 'running'; h.subject.renderProductRuntime(s);
  h.subject.showInterviewRuntimeError(new Error('offline'));
  assert.match(notice(h), /Не удалось обновить состояние/);
  assert.doesNotMatch(notice(h), /Ожидайте завершения|Обработка продолжается|сейчас не расходуется/);
  h.subject.restoreInterviewActionControls(); assert.match(notice(h), /Не удалось обновить состояние/);
  h.subject.renderProductRuntime(s); assert.match(notice(h), /Идёт обработка/);
});

test('C6 historical user Turn followed by a character is not a current answer receipt', () => {
  const h = setup(), s = waiting(h);
  s.trace.turns.push({ turn_id: 'later-character', sequence_no: 22, speaker_type: 'character', content_text: 'Реплика' });
  h.subject.renderProductRuntime(s); assert.doesNotMatch(notice(h), /Ответ сохранён/);
  h.subject.showInterviewRuntimeError(new Error('offline')); assert.doesNotMatch(notice(h), /Ответ сохранён/);
});

test('C5 answered clarification leaves only server-permitted finish, without an invitation to disabled input', () => {
  const h = setup(), s = waiting(h);
  s.clarification = { id: 'clarification', status: 'ASK', response_outcome: 'answered', answer_turn_id: 'last-answer' };
  s.finish_availability = { allowed: true }; s.blocking_system_wait = false;
  h.subject.renderProductRuntime(s); assert.equal(h.textarea.disabled, true);
  assert.doesNotMatch(h.textarea.placeholder, /Введите|Поясните|Напишите/);
  assert.equal(h.controls.finish.disabled, false); assert.equal(h.controls.finish.classList.contains('hidden'), false);
  assert.doesNotMatch(notice(h), /Ожидайте|Обработка/);
});

test('C6 active background AI allows send; confirmed blocking wait preserves editable draft', () => {
  const h = setup(), s = h.snapshot(20); s.pipeline = { status: 'running' }; s.blocking_system_wait = false;
  h.subject.renderProductRuntime(s); assert.equal(h.controls.submit.disabled, false); assert.equal(h.textarea.disabled, false);
  s.blocking_system_wait = true; h.subject.renderProductRuntime(s);
  assert.equal(h.controls.submit.disabled, true); assert.equal(h.textarea.disabled, false);
  s.blocking_system_wait = false; h.subject.renderProductRuntime(s);
  assert.equal(h.controls.submit.disabled, false); assert.doesNotMatch(notice(h), /Ожидайте завершения/);
});

test('C4 successful send and a new ASK/AS always show action labels, without a receipt timeout', async () => {
  const h = setup();
  const wiring = fs.readFileSync(new URL('../../web/js/wiring.js', import.meta.url), 'utf8');
  h.context.loadInterview = async () => h.subject;
  vm.runInContext(wiring.slice(wiring.indexOf('let failedInterviewMessage ='), wiring.indexOf("interviewForm.addEventListener('submit'"))
    + '\nglobalThis.submit = submitCurrentInterviewAnswer;', h.context);
  h.setFetch(async (_url, options) => {
    if (options?.method === 'POST') {
      const body = JSON.parse(options.body); const turn = { turn_id: body.turn_id, request_id: body.request_id,
        content_text: body.content, sequence_no: 30, speaker_type: 'assessee' };
      h.runtime.trace.turns.push(turn); return json({ turn });
    }
    return json(h.runtime);
  });
  h.textarea.value = 'Ответ'; await h.context.submit();
  assert.equal(h.context.interviewSubmitLabel.textContent, 'Отправить');
  const ask = waiting(h); ask.clarification = { id: 'new-ask', status: 'ASK', question_turn_id: 'q', question: { text: 'Почему?' } };
  h.subject.renderProductRuntime(ask); assert.equal(h.context.interviewSubmitLabel.textContent, 'Отправить');
  h.subject.renderProductRuntime(h.snapshot(0, 'as-b')); h.flush();
  assert.equal(h.context.interviewSubmitLabel.textContent, 'Отправить');
});

test('C6 conclusive receipt read survives retirement of the pending operation and a failed runtime GET', async () => {
  const h = setup(); h.textarea.value = 'Принятый ответ';
  const op = h.subject.prepareProductInterviewAnswer(h.textarea.value, h.textarea.value);
  const key = `agent4k.assessmentPending:${op.cycleId}:${op.situationId}:${op.ownerId}`;
  h.storage.set(key, JSON.stringify({ ...JSON.parse(h.storage.get(key)), status: 'unknown' }));
  h.setFetch(() => json({ status: 'accepted', processing_status: 'applied', cycle_id: op.cycleId,
    assessment_situation_id: op.situationId, request_id: op.requestId, turn_id: op.turnId, clarification_id: null,
    turn: { turn_id: op.turnId, request_id: op.requestId, content_text: op.text, speaker_type: 'assessee' } }));
  h.context.loadProductRuntime = async () => { throw new Error('runtime unavailable'); };
  const result = await h.subject.sendProductInterviewAnswer(op.text);
  assert.equal(result.accepted, true); assert.equal(h.subject.readProductInterviewAnswer(), null);
  assert.match(notice(h), /Не удалось обновить состояние/);
  assert.doesNotMatch(notice(h), /продолжается|Ожидайте завершения|сейчас не расходуется/);
});

test('C4 server-blocked preflight keeps the action label without inventing a send failure', async () => {
  const h = setup();
  const wiring = fs.readFileSync(new URL('../../web/js/wiring.js', import.meta.url), 'utf8');
  h.context.loadInterview = async () => h.subject;
  vm.runInContext(wiring.slice(wiring.indexOf('let failedInterviewMessage ='), wiring.indexOf("interviewForm.addEventListener('submit'"))
    + '\nglobalThis.submit = submitCurrentInterviewAnswer;', h.context);
  const s = waiting(h); h.setFetch(() => json(s)); h.textarea.value = 'Черновик до изменения состояния';
  await h.context.submit(); assert.equal(h.controls.submit.disabled, true);
  assert.equal(h.context.interviewSubmitLabel.textContent, 'Отправить');
  assert.equal(h.fetchCalls.some(([, options]) => options?.method === 'POST'), false);
  assert.equal(h.textarea.value, 'Черновик до изменения состояния');
});
