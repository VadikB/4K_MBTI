import assert from 'node:assert/strict';
import fs from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';
import { createInterviewHarness } from './helpers/p3-a-interview.mjs';

const interview = fs.readFileSync('web/js/screens/interview.js', 'utf8');
const wiring = fs.readFileSync('web/js/wiring.js', 'utf8');
const section = (source, from, to) => source.slice(source.indexOf(from), source.indexOf(to)).replaceAll('export const ', 'const ');
const tick = async () => { for (let i = 0; i < 30; i += 1) await Promise.resolve(); };
const deferred = () => {
  let resolve, reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
};
const json = (value) => new Response(JSON.stringify(value), { headers: { 'Content-Type': 'application/json' } });
const input = (h, value) => { h.textarea.value = value; h.textarea.listeners.get('input')(); };
const setup = () => {
  const h = createInterviewHarness();
  h.subject.initInterview();
  h.runtime = h.snapshot();
  h.subject.renderProductRuntime(h.runtime); h.flush();
  h.context.clearConfirmedReturnContinue = () => {};
  h.context.renderReturnCard = () => {};
  h.context.returnClientId = 'owned-browser';
  h.context.openProcessing = () => { h.state.currentScreen = 'processing'; };
  h.context.window.setInterval = (callback) => { h.poll = callback; return 99; };
  h.context.window.clearInterval = () => {};
  vm.runInContext(`
    let productRuntimePollGeneration = 0;
    let returnHeartbeatTimer = null, returnPresenceCycleId = null, returnPresenceGeneration = 0;
    const PRODUCT_RUNTIME_POLL_MS = 1200;
    ${section(interview, 'const heartbeatProductPresence =', '\nconst renderReturnCard =')}
    ${section(interview, 'const loadReturnState =', '\nexport const parseInterviewAssistantMessage =')}
    ${section(interview, 'export const resumeProductRuntimePolling =', '\nexport const openInterview =')}
    globalThis.runtimeSubject = {loadProductRuntime, loadReturnState, startProductPresence, stopProductPresence,
      toggleProductPause, finishProductAssessment, createProductAdditionalSession, resumeProductRuntimePolling,
      nextGeneration: () => { productRuntimePollGeneration += 1; }};
  `, h.context);
  Object.assign(h.subject, h.context.runtimeSubject);
  h.subject.clearInterviewTimer = () => {};
  h.setFetch(async (url) => String(url).includes('/return-state')
    ? json({ cycle_id: h.state.productCycleId, allowed_action: 'none' }) : json(h.runtime));
  return h;
};

const installActionHandlers = (h, module = h.subject) => {
  h.context.loadInterview = async () => module;
  h.context.window.confirm = () => true;
  h.context.interviewSubmitLabel = { textContent: '' };
  vm.runInContext(section(wiring, 'let failedInterviewMessage =', '\nconst sendInterviewAnswer =')
    + section(wiring, 'let interviewActionGeneration =', '\ninterviewGoProcessingButton.addEventListener'), h.context);
  return {
    finish: h.context.interviewFinishButton.listeners.get('click'),
    pause: h.context.interviewPauseButton.listeners.get('click'),
    additional: h.context.interviewAdditionalButton.listeners.get('click'),
  };
};

test('F07 actual Finish/Pause/Additional handlers normalize rejected network calls and retain business reasons', async () => {
  for (const action of ['finish', 'pause', 'additional']) {
    const h = setup();
    const handlers = installActionHandlers(h);
    h.setFetch(async () => { throw new TypeError('Failed to fetch'); });
    await handlers[action]();
    assert.match(h.errors.at(-1), /Проверьте соединение/);
    assert.doesNotMatch(h.errors.at(-1), /Failed to fetch/);
    const business = 'Назначение оценки отменено администратором.';
    h.context.loadInterview = async () => ({ ...h.subject,
      finishProductAssessment: async () => { throw new Error(business); },
      toggleProductPause: async () => { throw new Error(business); },
      createProductAdditionalSession: async () => { throw new Error(business); },
    });
    await handlers[action]();
    assert.equal(h.errors.at(-1), business);
  }
});

test('F08 rejected polling and heartbeat retain unknown answer recovery and its original operation', async () => {
  for (const channel of ['poll', 'presence']) {
    const h = setup();
    input(h, 'Собственный ответ');
    const operation = h.subject.prepareProductInterviewAnswer(h.textarea.value, h.textarea.value);
    const key = `agent4k.assessmentPending:${operation.cycleId}:${operation.situationId}:${operation.ownerId}`;
    const pending = JSON.parse(h.storage.get(key)); pending.status = 'unknown';
    h.storage.set(key, JSON.stringify(pending));
    h.setFetch(async () => { throw new TypeError('Failed to fetch'); });
    h.subject.renderProductRuntime(h.runtime);
    const row = h.messages.children.find((item) => item.dataset.deliveryRequestId === operation.requestId);
    assert.ok(row, 'the original operation has its delivery/recovery row');
    if (channel === 'poll') { h.subject.resumeProductRuntimePolling(); h.poll(); }
    else h.subject.startProductPresence();
    await tick();
    assert.match(h.errors.at(-1), /исход отправки.*кнопкой в сообщении/);
    assert.doesNotMatch(h.errors.at(-1), /Текст сохранён|текст сохранён/);
    assert.equal(h.controls.submit.disabled, true);
    assert.equal(h.controls.finish.disabled, true);
    assert.equal(JSON.parse(h.storage.get(key)).requestId, operation.requestId);
    assert.equal(JSON.parse(h.storage.get(key)).turnId, operation.turnId);
    assert.ok(h.messages.children.includes(row), 'background error retains the recovery action');
    h.context.window.sessionStorage.getItem = () => { throw new Error('Storage read failed after dispatch'); };
    h.subject.showInterviewRuntimeError(new TypeError('Failed to fetch'));
    assert.match(h.errors.at(-1), /исход отправки.*кнопкой в сообщении/);
    assert.equal(h.controls.submit.disabled, true);
    assert.equal(h.controls.finish.disabled, true);
    h.subject.stopProductPresence();
  }
});

test('F08 storage value/context failure never promises current draft revision is saved', async () => {
  for (const failedPart of ['value', 'context', 'read']) {
    const h = setup();
    input(h, 'Прежняя редакция');
    const storage = h.context.window.sessionStorage;
    const originalSet = storage.setItem, originalGet = storage.getItem;
    storage.setItem = (key, value) => {
      if (failedPart === 'value' || (failedPart === 'context' && key.endsWith(':context'))) {
        throw new Error('Quota exceeded');
      }
      return originalSet(key, value);
    };
    if (failedPart === 'read') storage.getItem = () => { throw new Error('Storage is disabled'); };
    assert.doesNotThrow(() => input(h, 'Текущая редакция'));
    h.setFetch(async () => { throw new TypeError('Failed to fetch'); });
    h.subject.resumeProductRuntimePolling(); h.poll(); await tick();
    assert.match(h.errors.at(-1), /Сохранение введённого текста не подтверждено/);
    assert.doesNotMatch(h.errors.at(-1), /Введённый текст сохранён/);
    assert.equal(h.textarea.value, 'Текущая редакция');
    assert.equal(h.subject.isCurrentInterviewDraftSaved(), false);
    storage.getItem = originalGet;
  }
  const h = setup(); input(h, 'Успешно записанная текущая редакция');
  h.setFetch(async () => { throw new TypeError('Failed to fetch'); });
  h.subject.resumeProductRuntimePolling(); h.poll(); await tick();
  assert.match(h.errors.at(-1), /Введённый текст сохранён/);
});

test('F08 active pending POST retains recovery priority when a poll fails before its receipt', async () => {
  const h = setup(); const pending = deferred();
  input(h, 'Собственный ожидающий ответ');
  h.setFetch(async (url, options) => options?.method === 'POST' ? pending.promise : json(h.runtime));
  const sending = h.subject.sendProductInterviewAnswer(h.textarea.value); await tick();
  h.setFetch(async () => { throw new TypeError('Failed to fetch'); });
  h.subject.resumeProductRuntimePolling(); h.poll(); await tick();
  assert.match(h.errors.at(-1), /исход отправки.*кнопкой в сообщении/);
  assert.equal(h.controls.submit.disabled, true); assert.equal(h.controls.finish.disabled, true);
  pending.reject(new TypeError('Failed to fetch')); await sending; await tick();
  assert.match(h.errors.at(-1), /исход отправки/);
});

const switches = {
  owner: (h) => { h.state.pendingUser = { id: 9 }; },
  epoch: (h) => { h.state.identityEpoch += 1; },
  cycle: (h) => { h.state.productCycleId = 'cycle-b'; },
  situation: (h) => { h.state.productAssessmentSituationId = 'as-b'; },
  screen: (h) => { h.state.currentScreen = 'home'; },
  generation: (h) => h.subject.nextGeneration(),
  view: (h) => h.context.advanceAssessmentViewGeneration(),
};

test('F09 actual rejected return/runtime polling requests cannot alter a newer owner/epoch/Cycle/AS/screen/generation', async () => {
  for (const request of ['return-state', 'runtime']) {
    for (const change of Object.values(switches)) {
      const h = setup(); const pending = deferred();
      h.setFetch(async (url) => request === 'runtime' && String(url).includes('/return-state')
        ? json({ cycle_id: 'cycle-a', allowed_action: 'none' }) : pending.promise);
      h.subject.resumeProductRuntimePolling(); h.poll(); await tick();
      change(h);
      h.errors.push('Сообщение новой оценки');
      input(h, 'Текст новой оценки');
      const count = h.errors.length, value = h.textarea.value;
      pending.reject(new TypeError('Failed to fetch')); await tick();
      assert.equal(h.errors.length, count);
      assert.equal(h.textarea.value, value);
    }
  }
});

test('F09 default runtime load captures generation across navigation back to the same owner/Cycle/AS', async () => {
  const h = setup(); const pending = deferred();
  h.setFetch(() => pending.promise);
  const loading = h.subject.loadProductRuntime().catch(h.subject.showInterviewRuntimeError);
  h.state.currentScreen = 'home'; h.subject.nextGeneration(); h.state.currentScreen = 'interview';
  h.errors.push('Сообщение после возврата'); const count = h.errors.length;
  pending.reject(new TypeError('Failed to fetch')); await loading;
  assert.equal(h.errors.length, count);
});

test('F09 rejected presence is scoped to identity/Cycle/AS and its own heartbeat generation', async () => {
  for (const [name, change] of Object.entries(switches)) {
    const h = setup(); const pending = deferred();
    h.setFetch(() => pending.promise);
    h.subject.startProductPresence();
    if (name === 'generation') h.subject.stopProductPresence(); else change(h);
    h.errors.push('Новое сообщение'); const count = h.errors.length;
    pending.reject(new TypeError('Failed to fetch')); await tick();
    assert.equal(h.errors.length, count);
    assert.equal(h.callbacks.size, 0, 'stale presence does not schedule a heartbeat for the new scope');
  }
  const h = setup(); h.setFetch(async () => { throw new TypeError('Failed to fetch'); });
  h.subject.startProductPresence(); await tick();
  assert.match(h.errors.at(-1), /Проверьте соединение/);
  assert.ok(h.callbacks.size > 0, 'current failure retains its own retry');
  h.subject.stopProductPresence();
});

test('F09 actual action handlers ignore late rejection/finally after owner/Cycle/AS and action generation change', async () => {
  for (const action of ['finish', 'pause', 'additional']) {
    for (const name of ['owner', 'epoch', 'cycle', 'situation', 'screen', 'generation', 'view']) {
      const h = setup(); const pending = deferred();
      const handlers = installActionHandlers(h);
      h.setFetch(() => pending.promise);
      const running = handlers[action](); await tick();
      if (name === 'generation') {
        h.context.loadInterview = async () => ({ ...h.subject, toggleProductPause: async () => {} });
        await handlers.pause();
      } else switches[name](h);
      h.errors.push('Сообщение новой оценки'); const count = h.errors.length;
      h.context.interviewAdditionalButton.disabled = true;
      pending.reject(new TypeError('Failed to fetch')); await running; await tick();
      assert.equal(h.errors.length, count, `${action}/${name}`);
      assert.equal(h.context.interviewAdditionalButton.disabled, true, `${action}/${name} cannot re-enable the new control`);
    }
  }
});

test('F09 same-scope re-entry cannot revive a rejected old send or action', async () => {
  for (const action of ['send', 'pause']) {
    const h = setup(); const pending = deferred();
    const handlers = installActionHandlers(h);
    input(h, action === 'send' ? 'Старый ответ' : '');
    h.setFetch(() => pending.promise);
    const running = action === 'send' ? h.subject.sendProductInterviewAnswer(h.textarea.value) : handlers.pause();
    await tick();
    h.state.currentScreen = 'home'; h.context.advanceAssessmentViewGeneration();
    h.state.currentScreen = 'interview'; h.context.advanceAssessmentViewGeneration();
    input(h, 'Новая редакция после возврата');
    h.errors.push('Сообщение после возврата'); const count = h.errors.length;
    pending.reject(new TypeError('Failed to fetch')); await running; await tick();
    assert.equal(h.errors.length, count, action);
    assert.equal(h.textarea.value, 'Новая редакция после возврата', action);
  }
});
