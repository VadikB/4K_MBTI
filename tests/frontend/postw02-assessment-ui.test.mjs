import assert from 'node:assert/strict';
import test from 'node:test';
import vm from 'node:vm';
import { createInterviewHarness } from './helpers/exec01-lifecycle-harness.mjs';

const json = (body) => new Response(JSON.stringify(body), { headers: { 'Content-Type': 'application/json' } });
const pending = (h) => ({ ...h.snapshot(2),
  current_situation: { ...h.snapshot().current_situation, status: 'scenario_ended' },
  participant_progress: { planned_total: 8, current_position_no: 3 },
  finish_availability: { allowed: false, reason: 'ANALYSIS_PENDING' }, pipeline: { status: 'running' } });
const scopeFetch = (h, value) => h.setFetch(async (url, options) => {
  assert.notEqual(options?.method, 'POST', 'status check never creates a Turn/operation');
  if (String(url).endsWith('/return-state')) return json({ cycle_id: 'cycle-a', allowed_action: 'none' });
  assert.ok(String(url).endsWith('/runtime'));
  return json(value);
});

for (const completed of [undefined, null, 0, 2]) test(`shared projection wins with completed=${completed}`, () => {
  const h = createInterviewHarness({ meta: true });
  const saved = pending(h);
  saved.route = { positions: [{ position_no: 1, current_assessment_situation_id: 'as-a' }],
    progress: { total_positions: 1, completed_positions: completed } };
  h.subject.renderProductRuntime(saved);
  assert.equal(h.context.interviewCaseBadge.textContent, 'Ситуация 3 из 8');
  saved.participant_progress.current_position_no = null;
  h.subject.renderProductRuntime(saved);
  assert.equal(h.context.interviewCaseBadge.textContent, 'Всего ситуаций: 8');
  saved.current_situation = null; saved.between_situations = true;
  saved.participant_progress.last_completed_position_no = 3;
  h.subject.renderProductRuntime(saved);
  assert.equal(h.messages.firstChild.children[1].textContent, 'Ситуация 3 завершена');
  assert.equal(h.state.assessmentCaseNumber, 3, 'next position is not presented implicitly');
});

test('45 seconds and repeated manual GET keep pending neutral, reuse budget and never open finish', async () => {
  const h = createInterviewHarness();
  h.context.clockTime = 1000;
  vm.runInContext('Date.now = () => clockTime', h.context);
  const saved = pending(h);
  h.subject.renderProductRuntime(saved);
  const deadline = h.subject.productProcessingBudget(saved);
  assert.equal(h.subject.productRuntimePollAllowed(), true);
  h.context.clockTime += 45001;
  assert.equal(h.subject.productRuntimePollAllowed(), false);
  scopeFetch(h, saved);
  await assert.rejects(h.subject.waitForProductClarification(), { name: 'ClarificationWaitLimit' });
  for (let n = 0; n < 2; n++) {
    const button = h.context.interviewError.children.at(-1);
    await button.listeners.get('click')();
    assert.equal(h.context.interviewError.dataset.tone, 'neutral');
    assert.match(h.errors.at(-1), /Обработка занимает больше времени/);
    assert.equal(h.subject.productProcessingBudget(saved), deadline);
    assert.equal(h.subject.productRuntimePollAllowed(), false);
    assert.equal(h.controls.finish.disabled, true);
  }
  assert.equal(h.fetchCalls.length, 4, 'two GETs per manual check; no endless polling');
});

test('failed, WAIT_TECHNICAL and unreadable state have distinct feedback; ASK is server-owned', async () => {
  const h = createInterviewHarness();
  const saved = pending(h);
  h.subject.renderProductRuntime(saved);
  h.setFetch(async () => { throw new TypeError('offline'); });
  await h.context.interviewError.children.at(-1).listeners.get('click')();
  assert.equal(h.errors.at(-1), 'Не удалось обновить состояние');
  assert.equal(h.context.interviewError.dataset.tone, 'failed');
  saved.pipeline.status = 'failed';
  h.subject.renderProductRuntime(saved);
  assert.equal(h.context.interviewError.dataset.tone, 'failed');
  assert.match(h.errors.at(-1), /Произошла ошибка обработки/);
  saved.pipeline.status = 'running'; saved.finish_availability.reason = 'WAIT_TECHNICAL';
  h.subject.renderProductRuntime(saved);
  assert.equal(h.context.interviewError.dataset.tone, 'neutral');
  assert.match(h.errors.at(-1), /требует проверки/);
  assert.equal(h.subject.productRuntimePollAllowed(), false);
  saved.clarification = { id: 'ask-1', status: 'ASK', question_turn_id: 'q-1', question: { text: 'Почему?' } };
  h.subject.renderProductRuntime(saved);
  assert.equal(h.controls.textarea.disabled, false);
  assert.equal(h.controls.finish.disabled, true);
  saved.clarification.response_outcome = 'answered';
  h.subject.renderProductRuntime(saved);
  assert.equal(h.controls.finish.disabled, true);
  saved.finish_availability = { allowed: true };
  h.subject.renderProductRuntime(saved);
  assert.equal(h.controls.finish.disabled, false);
});

test('ordinary active actions never pause or interrupt; existing saved recovery remains', async () => {
  const h = createInterviewHarness();
  let saved = h.snapshot(2);
  h.subject.renderProductRuntime(saved);
  assert.equal(h.context.interviewPauseButton.classList.contains('hidden'), true);
  assert.equal(h.context.interviewAdditionalButton.classList.contains('hidden'), true);
  scopeFetch(h, saved);
  await h.subject.toggleProductPause();
  await h.subject.createProductAdditionalSession();
  assert.equal(h.fetchCalls.some(([, options]) => options?.method === 'POST'), false);
  saved = { ...saved, status: { collection_status: 'paused' } };
  h.subject.renderProductRuntime(saved);
  assert.equal(h.context.interviewPauseButton.classList.contains('hidden'), false);
  saved.status.collection_status = 'interrupted'; saved.continuation = { status: 'pending', intent_id: 'saved-intent' };
  h.subject.renderProductRuntime(saved);
  assert.equal(h.context.interviewAdditionalButton.classList.contains('hidden'), false);
});

test('late status read cannot paint another screen or owner', async () => {
  const h = createInterviewHarness();
  const saved = pending(h);
  h.subject.renderProductRuntime(saved);
  let release;
  const gate = new Promise((resolve) => { release = resolve; });
  h.setFetch(async (url) => String(url).endsWith('/return-state')
    ? json({ cycle_id: 'cycle-a', allowed_action: 'none' }) : gate);
  const check = h.context.interviewError.children.at(-1).listeners.get('click')();
  for (let i = 0; i < 10; i++) await Promise.resolve();
  h.state.currentScreen = 'dashboard'; h.state.identityEpoch++;
  const messages = h.messages.firstChild;
  release(json({ ...saved, clarification: { status: 'ASK', id: 'late-question' } }));
  await check;
  assert.equal(h.messages.firstChild, messages);
  assert.equal(h.controls.finish.disabled, true);
});


test('interrupted recovery after a lost additional-session receipt reuses its consumed intent', async () => {
  const h = createInterviewHarness();
  const saved = { ...h.snapshot(2), status: { collection_status: 'interrupted' },
    continuation: { status: 'consumed', intent_id: 'saved-intent' } };
  h.subject.renderProductRuntime(saved);
  assert.equal(h.context.interviewAdditionalButton.classList.contains('hidden'), false);
  h.setFetch(async (url, options) => {
    if (String(url).endsWith('/return-state')) return json({ cycle_id: 'cycle-a', allowed_action: 'none' });
    if (String(url).endsWith('/runtime')) return json(saved);
    assert.equal(options.method, 'POST');
    if (String(url).endsWith('/next')) return json({ decision: { status: 'SELECTED',
      assessment_situation_id: 'next-as' }, plan: { revision_id: 'saved-plan' } });
    assert.ok(String(url).endsWith('/present-next'));
    assert.deepEqual(JSON.parse(options.body), { assessment_situation_id: 'next-as', expected_plan_revision_id: 'saved-plan' });
    return json({ presentation: { assessment_situation_id: 'next-as' } });
  });
  await h.subject.createProductAdditionalSession();
  assert.equal(h.fetchCalls.filter(([, options]) => options?.method === 'POST').length, 2);
  assert.equal(h.fetchCalls.some(([url]) => String(url).endsWith('/additional-sessions')), false);
});


test('05 UI unresolved draft conflict blocks direct send and remains blocked after runtime refresh', async () => {
  const h = createInterviewHarness();
  h.subject.renderProductRuntime(h.snapshot(2));
  h.context.draftSlot = () => 'dialogue:fixture';
  vm.runInContext('durableDraft = { conflicted: () => true, bind() {}, saved: () => true }', h.context);
  const result = await h.subject.sendProductInterviewAnswer('Не выбранная редакция');
  assert.equal(result.accepted, false); assert.equal(h.fetchCalls.length, 0);
  assert.match(h.errors.at(-1), /Выберите, с каким текстом/);
  h.subject.renderProductRuntime(h.snapshot(2));
  assert.equal(h.context.interviewSubmitButton.disabled, true);
});
