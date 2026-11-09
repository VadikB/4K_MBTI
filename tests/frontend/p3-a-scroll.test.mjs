import assert from 'node:assert/strict';
import test from 'node:test';
import { createInterviewHarness as harness } from './helpers/p3-a-interview.mjs';

test('P3-A opens long restored/new AS at its beginning without scrolling each saved Turn', () => {
  const h = harness();
  h.subject.renderProductRuntime(h.snapshot(8));
  assert.equal(h.calls.length, 1, 'saved history is rendered as one scroll batch');
  h.flush();
  assert.equal(h.area.scrollTop, 0);
  assert.equal(h.button.hidden, false);
  h.area.scrollTop = 600;
  h.subject.renderProductRuntime(h.snapshot(9, 'as-b'));
  h.flush();
  assert.equal(h.area.scrollTop, 0, 'the next AS starts at its own introduction');
});

test('P3-A renders only public fields of delivered string/structured materials', () => {
  const h = harness();
  const event = (content, type = 'material_disclosed', extra = {}) => ({
    event_type: type, payload_json: { content, recipient: 'assessee', ...extra },
  });
  assert.equal(h.subject.productEventText(event('Разрешённый текст')), 'Разрешённый текст');
  assert.equal(h.subject.productEventText(event({ title: 'Письмо', text: 'Разрешённый текст',
    criteria: 'HIDDEN', scenario: 'HIDDEN', metadata: { text: 'HIDDEN' } })), 'Письмо: Разрешённый текст');
  assert.equal(h.subject.productEventText(event({ name: 'Документ', content: 'Содержание' }, 'mandatory_update')),
    'Документ: Содержание');
  assert.equal(h.subject.productEventText(event({ label: 'Памятка', description: 'Описание' })), 'Памятка: Описание');
  assert.equal(h.subject.productEventText(event({ criteria: 'HIDDEN', nested: { text: 'HIDDEN' } })), null);
  assert.equal(h.subject.productEventText(event({ title: 'Название', text: { private: 'HIDDEN' } })), 'Название');
  assert.equal(h.subject.productEventText(event(['HIDDEN'])), null);
  assert.equal(h.subject.productEventText(event('HIDDEN', 'semantic_decision')), null);
  assert.equal(h.subject.productEventText(event('HIDDEN', 'character_response')), null);
  assert.equal(h.subject.productEventText(event('HIDDEN', 'material_disclosed', { recipient: 'evaluator' })), null);
});

test('P3-A hides only the identical initial material mirror and retains later same-ID content/updates', () => {
  const h = harness();
  const saved = h.snapshot();
  const initial = { material_id: 'm-start', title: 'Начальное письмо', text: 'Стартовое содержание',
    scenario: 'HIDDEN-SCENARIO', criteria: 'HIDDEN-CRITERIA' };
  saved.current_situation.participant_payload.initial_materials = [initial];
  saved.trace.events = [
    { event_type: 'material_disclosed', sequence_no: 1, material_id: 'm-start',
      payload_json: { content: initial, recipient: 'assessee' } },
    { event_type: 'material_disclosed', sequence_no: 2, material_id: 'm-start',
      payload_json: { content: { title: 'Начальное письмо', text: 'Позднее раскрытие того же ID' }, recipient: 'assessee' } },
    { event_type: 'mandatory_update', sequence_no: 3, material_id: 'm-start',
      payload_json: { content: { title: 'Обновление письма', text: 'Новые условия' }, recipient: 'assessee' } },
    { event_type: 'mandatory_update', sequence_no: 4, material_id: 'm-start',
      payload_json: { content: initial, recipient: 'assessee' } },
    { event_type: 'semantic_decision', sequence_no: 5,
      payload_json: { content: 'HIDDEN-DECISION' } },
  ];
  h.subject.renderProductRuntime(saved); h.flush();
  const text = (node) => [node.textContent || '', ...node.children.map(text)].join(' ');
  const visible = text(h.messages);
  assert.equal(h.messages.children.length, 4, 'one start bubble and three public events');
  assert.equal(visible.split('Стартовое содержание').length - 1, 2,
    'only the initial mirror is hidden; a mandatory update is retained even with identical content');
  assert.ok(visible.includes('Позднее раскрытие того же ID'));
  assert.ok(visible.includes('Новые условия'));
  assert.ok(!visible.includes('HIDDEN'));
  assert.ok(!visible.includes('[object Object]'));
  assert.equal(h.messages.children[0].querySelector('.interview-bubble').dataset.speakerLabel, '4К Ассистент');
  assert.equal(h.messages.children[1].querySelector('.interview-bubble').dataset.speakerLabel, 'Материал ситуации');
  assert.equal(h.messages.children[2].querySelector('.interview-bubble').dataset.speakerLabel, 'Материал ситуации');
  h.subject.renderProductRuntime(saved); h.flush();
  assert.equal(h.messages.children.length, 4, 'unchanged readback creates no extra event bubbles');
});

test('P3-A new saved dialogue preserves the reader position and unchanged polls never reposition it', () => {
  const h = harness();
  h.subject.renderProductRuntime(h.snapshot(3)); h.flush();
  h.area.scrollTop = 420;
  h.calls.length = 0;
  h.subject.renderProductRuntime(h.snapshot(5));
  assert.equal(h.calls.length, 1);
  h.flush();
  assert.equal(h.area.scrollTop, 420);
  assert.equal(h.button.hidden, false);
  const node = h.messages.firstChild;
  h.area.scrollTop = 280;
  h.calls.length = 0;
  h.subject.renderProductRuntime(h.snapshot(5)); h.flush();
  assert.equal(h.messages.firstChild, node);
  assert.equal(h.area.scrollTop, 280);
  assert.equal(h.calls.length, 0);
});

test('P3-A follows a new saved reply only when the reader was already at the end', () => {
  const h = harness();
  h.subject.renderProductRuntime(h.snapshot(3)); h.flush();
  h.area.scrollTop = h.area.scrollHeight - h.area.clientHeight - 12;
  h.subject.renderProductRuntime(h.snapshot(4)); h.flush();
  assert.equal(h.area.scrollTop, h.area.scrollHeight - h.area.clientHeight);
  assert.equal(h.button.hidden, true);
});

test('P3-A assistant/delivery updates preserve reading; explicit own send can reveal its row', () => {
  const h = harness();
  h.subject.renderProductRuntime(h.snapshot(2)); h.flush();
  h.area.scrollTop = 350;
  h.subject.addInterviewMessage('assistant', 'New public reply');
  assert.equal(h.area.scrollTop, 350);
  const row = h.subject.addInterviewMessage('user', 'Synthetic answer', null, { scroll: false });
  h.subject.setInterviewMessageDeliveryState(row, 'failed');
  assert.equal(h.area.scrollTop, 350);
  h.subject.addInterviewMessage('user', 'Explicit answer');
  assert.equal(h.area.scrollTop, h.area.scrollHeight - h.area.clientHeight);
  assert.ok(h.calls.every((call) => call.behavior === 'instant'));
});

test('P3-A deferred alignment yields when a participant scrolls between layout callbacks', () => {
  const h = harness();
  h.subject.renderProductRuntime(h.snapshot(3));
  h.area.scrollTop = 200;
  h.flush();
  assert.equal(h.area.scrollTop, 200);
  assert.equal(h.callbacks.size, 0);
});

test('P3-A stale callbacks cannot move a new Cycle, AS, screen, or replaced DOM', () => {
  for (const change of [
    (h) => { h.state.productCycleId = 'cycle-b'; },
    (h) => { h.state.activeInterviewCaseKey = 'as-b'; },
    (h) => { h.state.currentScreen = 'prechat'; },
    (h) => { h.messages.innerHTML = ''; },
  ]) {
    const h = harness();
    h.subject.renderProductRuntime(h.snapshot(3)); h.flush();
    h.subject.scheduleInterviewBottomAlignment();
    change(h);
    h.area.scrollTop = 125;
    h.calls.length = 0;
    h.flush();
    assert.equal(h.area.scrollTop, 125);
    assert.equal(h.calls.length, 0);
  }
});

test('P3-A a newer alignment cancels older RAF/timers even when an old callback is delivered late', () => {
  const h = harness();
  h.subject.renderProductRuntime(h.snapshot(3)); h.flush();
  h.subject.scheduleInterviewBottomAlignment();
  const staleCallbacks = [...h.callbacks.values()];
  h.subject.scheduleInterviewScrollAlignment({ top: 0 });
  assert.equal(h.callbacks.size, 3, 'only the new RAF and two layout timers remain');
  staleCallbacks.forEach((callback) => callback());
  h.flush();
  assert.equal(h.area.scrollTop, 0);
});

test('P3-A reading/focus/leave cancel deferred work and the latest-messages button remains controlled', () => {
  const h = harness({ animationFrame: false });
  h.subject.initInterview();
  h.subject.renderProductRuntime(h.snapshot(3)); h.flush();
  for (const cancel of [
    () => h.area.listeners.get('wheel')(),
    () => h.area.listeners.get('touchstart')(),
    () => h.area.listeners.get('pointerdown')(),
    () => h.area.listeners.get('keydown')(),
    () => h.textarea.listeners.get('focus')(),
    () => h.leave(),
  ]) {
    h.subject.scheduleInterviewBottomAlignment();
    cancel();
    h.area.scrollTop = 180;
    h.flush();
    assert.equal(h.area.scrollTop, 180);
    assert.equal(h.callbacks.size, 0);
  }
  h.subject.scheduleInterviewScrollAlignment({ top: 180 });
  h.button.listeners.get('click')();
  h.flush();
  assert.equal(h.area.scrollTop, h.area.scrollHeight - h.area.clientHeight);
  assert.equal(h.calls.at(-1).behavior, 'smooth');
});
