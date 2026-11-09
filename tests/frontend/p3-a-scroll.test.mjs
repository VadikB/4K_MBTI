import assert from 'node:assert/strict';
import fs from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';

const source = fs.readFileSync(new URL('../../web/js/screens/interview.js', import.meta.url), 'utf8');
const section = (start, end) => source.slice(source.indexOf(start), source.indexOf(end));

// Execute the production renderer/message/scroll functions with a small DOM and
// deterministic layout callbacks. These tests do not simulate browser geometry,
// software keyboards, server state, or the submission contract.
const harness = ({ animationFrame = true } = {}) => {
  const callbacks = new Map();
  const calls = [];
  const listeners = new Map();
  let nextCallback = 0;
  const enqueue = (callback) => { callbacks.set(++nextCallback, callback); return nextCallback; };
  class Element {
    constructor() {
      this.children = [];
      this.dataset = {};
      this.style = {};
      this.className = '';
      this.isConnected = false;
      this.listeners = new Map();
      const classes = new Set();
      this.classList = {
        add: (...names) => names.forEach((name) => classes.add(name)),
        remove: (...names) => names.forEach((name) => classes.delete(name)),
        contains: (name) => classes.has(name),
        toggle: (name, enabled = !classes.has(name)) => enabled ? classes.add(name) : classes.delete(name),
      };
    }
    appendChild(child) { this.children.push(child); child.isConnected = true; return child; }
    append(...children) { children.forEach((child) => this.appendChild(child)); }
    set innerHTML(_value) { this.children.forEach((child) => { child.isConnected = false; }); this.children = []; }
    get firstChild() { return this.children[0] || null; }
    get lastElementChild() { return this.children.at(-1) || null; }
    setAttribute() {}
    addEventListener(name, handler) { this.listeners.set(name, handler); }
    querySelector(selector) {
      for (const child of this.children) {
        if (child.className.split(' ').includes(selector.slice(1))) return child;
        const nested = child.querySelector(selector);
        if (nested) return nested;
      }
      return null;
    }
    scrollIntoView() { assert.fail('History alignment must not scroll the outer document'); }
  }
  const messages = new Element();
  const shell = new Element();
  const area = new Element();
  area.clientHeight = 400;
  area.scrollTop = 0;
  Object.defineProperty(area, 'scrollHeight', {
    get: () => messages.children.reduce((height, child) => height
      + (child.className.includes('interview-message--situation') ? 1600 : 180), 0),
  });
  area.closest = () => shell;
  area.scrollTo = ({ top, behavior }) => {
    area.scrollTop = Math.max(0, Math.min(top, area.scrollHeight - area.clientHeight));
    calls.push({ top: area.scrollTop, behavior });
  };
  const button = new Element();
  const textarea = new Element();
  const state = { currentScreen: 'interview', productCycleId: 'cycle-a', activeInterviewCaseKey: null };
  let leaveCleanup;
  const context = vm.createContext({
    state, HTMLElement: Element,
    window: {
      requestAnimationFrame: animationFrame ? enqueue : undefined,
      cancelAnimationFrame: (id) => callbacks.delete(id),
      setTimeout: enqueue, clearTimeout: (id) => callbacks.delete(id),
      addEventListener: (name, handler) => listeners.set(name, handler),
      sessionStorage: { getItem() { return null; }, setItem() {}, removeItem() {} },
    },
    document: { createElement: () => new Element(), addEventListener() {} },
    MutationObserver: class { observe() {} },
    interviewMessages: messages, interviewScrollArea: area, interviewMessagesScroll: button,
    interviewTextarea: textarea, interviewCompactQuery: null, caseSidebarToggle: null,
    interviewPanel: new Element(), interviewCompleteActions: new Element(),
    interviewTimerBadge: new Element(), interviewSubmitButton: new Element(),
    interviewFinishButton: new Element(), interviewPauseButton: new Element(),
    interviewAdditionalButton: new Element(), interviewCaseStatus: new Element(),
    persistAssessmentContext() {}, restoreInterviewDraft() {},
    renderInterviewMeta() {}, renderCaseProgress() {}, updateInterviewTimer() {},
    parseInterviewAssistantMessage() { return null; },
    disableTextareaAssistFeatures() {}, placeInterviewTimerBadge() {},
    registerLeaveInterviewCleanup(handler) { leaveCleanup = handler; },
    clearInterviewTimer() {}, stopProductPresence() {}, pauseAssessmentTimerIfNeeded() {},
  });
  vm.runInContext(`
    let renderedProductMessages = null;
    let interviewScrollAlignmentGeneration = 0;
    let interviewScrollAlignmentFrame = null;
    let interviewScrollAlignmentTimers = [];
    ${section('const payloadText =', '\nconst renderProductRuntime =')}
    ${section('const renderProductRuntime =', '\nconst heartbeatProductPresence =')}
    ${section('const renderInterviewStructuredBlock =', '\nexport const addInterviewMessage =')}
    ${section('export const addInterviewMessage =', '\nconst isInterviewNearBottom =').replaceAll('export const ', 'const ')}
    ${section('const isInterviewNearBottom =', '\nconst getCurrentCaseDropdownLabel =')}
    ${section('export const initInterview =', '\nexport { startAssessmentInterview').replace('export const ', 'const ')}
    globalThis.subject = {renderProductRuntime, addInterviewMessage, setInterviewMessageDeliveryState,
      scheduleInterviewScrollAlignment, scheduleInterviewBottomAlignment, cancelInterviewScrollAlignment,
      productEventText, initInterview};
  `, context);
  const flush = () => {
    while (callbacks.size) {
      const batch = [...callbacks]; callbacks.clear();
      batch.forEach(([, callback]) => callback());
    }
  };
  const snapshot = (turnCount = 0, situationId = 'as-a', cycleId = 'cycle-a') => ({
    cycle_id: cycleId,
    current_situation: { assessment_situation_id: situationId, status: 'active', participant_payload: { title: 'Synthetic AS' } },
    route: { positions: [] }, status: { collection_status: 'active', remaining_seconds: 7200 },
    trace: { turns: Array.from({ length: turnCount }, (_, i) => ({
      turn_id: `turn-${i}`, sequence_no: i + 1,
      speaker_type: i % 2 ? 'assessee' : 'character', content_text: `Synthetic saved turn ${i}`,
    })), events: [] },
  });
  return { subject: context.subject, messages, area, button, textarea, state, callbacks, calls,
    listeners, flush, snapshot, leave: () => leaveCleanup() };
};

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
