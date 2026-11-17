import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import { createInterviewHarness } from './helpers/exec01-lifecycle-harness.mjs';
import { waitForProductCyclePreparation } from '../../web/js/product-cycle-preparation.js';

const json = (body) => new Response(JSON.stringify(body), { headers: { 'Content-Type': 'application/json' } });
const deferred = () => { let resolve, reject; const promise = new Promise((a, b) => { resolve = a; reject = b; }); return { promise, resolve, reject }; };
const tick = async () => { for (let i = 0; i < 25; i++) await Promise.resolve(); };
const between = (h, operation) => ({ ...h.snapshot(), current_situation: null, between_situations: true,
  status: { collection_status: 'paused', remaining_seconds: 7200 }, blocking_system_wait: false,
  preparation_operation: operation });
const button = (h) => h.messages.querySelector('.next-situation-button') || h.messages.querySelector('.primary-button');
const runtimeFetch = (h, runtime) => h.setFetch(async (url) => String(url).endsWith('/return-state')
  ? json({ cycle_id: 'cycle-a', allowed_action: 'connected' }) : runtime());

test('R1/R2: slow runtime and return-state reads coalesce while polling and manual checks continue', async () => {
  const h = createInterviewHarness(); h.subject.renderProductRuntime(h.snapshot(2));
  for (let round = 0; round < 3; round++) {
    const gate = deferred(); runtimeFetch(h, () => gate.promise);
    const reads = [h.subject.loadProductRuntime()]; await tick();
    for (let poll = 0; poll < 5; poll++) reads.push(h.subject.loadProductRuntime({ generation: poll === 0 ? null : undefined }));
    await tick();
    assert.equal(h.fetchCalls.length, (round + 1) * 2, 'one return-state + runtime per round');
    const saved = h.snapshot(3 + round); gate.resolve(json(saved)); await Promise.all(reads);
    assert.equal(h.state.assessmentRemainingSeconds, 7200);
    assert.equal(h.messages.children.length, 4 + round, 'each slow result applied without stopping polling');
  }
  const gate = deferred(); h.setFetch(() => gate.promise);
  const first = h.subject.loadProductRuntime(); const second = h.subject.loadProductRuntime(); await tick();
  assert.equal(h.fetchCalls.length, 7, 'also coalesces the first return-state GET');
  gate.reject(new TypeError('offline'));
  const failed = await Promise.allSettled([first, second]); assert.ok(failed.every(r => r.status === 'rejected'));
  runtimeFetch(h, () => json(h.snapshot(6))); await h.subject.loadProductRuntime();
  assert.equal(h.state.assessmentRemainingSeconds, 7200, 'failure releases the chain');
});

for (const change of ['owner', 'epoch', 'cycle', 'situation', 'screen', 'view', 'poll']) test(`R5: late GET rejected after ${change} change`, async () => {
  const h = createInterviewHarness(); h.subject.renderProductRuntime(h.snapshot(2));
  const gate = deferred(); runtimeFetch(h, () => gate.promise);
  const read = h.subject.loadProductRuntime(); await tick();
  if (change === 'owner') h.state.pendingUser = { id: 9 };
  if (change === 'epoch') h.state.identityEpoch++;
  if (change === 'cycle') h.state.productCycleId = 'other-cycle';
  if (change === 'situation') h.state.productAssessmentSituationId = 'other-as';
  if (change === 'screen') h.state.currentScreen = 'dashboard';
  if (change === 'view') h.context.advanceAssessmentViewGeneration();
  if (change === 'poll') vm.runInContext('productRuntimePollGeneration++', h.context);
  const card = h.messages.firstChild; gate.resolve(json(h.snapshot(4)));
  assert.equal(await read, null); assert.equal(h.messages.firstChild, card);
});

test('R5: new context can read while old context is pending; old completion cannot clear the new chain', async () => {
  const h = createInterviewHarness(); h.subject.renderProductRuntime(h.snapshot(2));
  const old = deferred(); runtimeFetch(h, () => old.promise);
  const a = h.subject.loadProductRuntime(); await tick(); h.state.identityEpoch++;
  const fresh = deferred(); runtimeFetch(h, () => fresh.promise);
  const b = h.subject.loadProductRuntime(); await tick();
  old.resolve(json(h.snapshot(8))); assert.equal(await a, null);
  const c = h.subject.loadProductRuntime(); await tick(); assert.equal(h.fetchCalls.length, 4);
  fresh.resolve(json(h.snapshot(3))); await Promise.all([b, c]); assert.equal(h.messages.children.length, 4);
});

for (const failure of ['timeout', 'network', 'completed']) test(`R3/R4: replaced Next button recovers after ${failure} and checks the same operation`, async () => {
  const h = createInterviewHarness(); h.subject.renderProductRuntime(between(h));
  h.context.waitForProductCyclePreparation = (accepted, options) => waitForProductCyclePreparation(accepted, { ...options, maxWaitMs: 0 });
  const gate = deferred(); let postedId;
  h.setFetch(async (url, options) => {
    if (options?.method === 'POST') { postedId = JSON.parse(options.body).idempotency_key; return gate.promise; }
    if (String(url).endsWith('/return-state')) return json({ cycle_id: 'cycle-a', allowed_action: 'connected' });
    if (String(url).includes('/preparation/')) return json({ operation_id: postedId, status: 'running' });
    return json(between(h, { operation_id: postedId, status: 'running' }));
  });
  const oldButton = button(h), click = oldButton.listeners.get('click')(); await tick();
  h.subject.renderProductRuntime(between(h, { operation_id: postedId, status: 'queued' }));
  const queuedButton = button(h); assert.notEqual(queuedButton, oldButton); assert.equal(queuedButton.disabled, true);
  await queuedButton.listeners.get('click')(); assert.equal(h.fetchCalls.length, 1, 'double dispatch blocked');
  h.subject.renderProductRuntime(between(h, { operation_id: postedId, status: 'running' }));
  const current = button(h); assert.equal(current.disabled, true);
  if (failure === 'completed') gate.resolve(json({ operation_id: postedId, status: 'completed', result: { decision: { status: 'SELECTED' } } }));
  else gate.reject(Object.assign(new Error(failure), { name: failure === 'timeout' ? 'TimeoutError' : 'TypeError' }));
  await click; assert.equal(button(h).disabled, false, 'connected action released immediately');
  // The same-status renderer fast path must also recalculate the button.
  h.subject.renderProductRuntime(between(h, { operation_id: postedId, status: 'running' }));
  assert.equal(button(h).disabled, false);
  await button(h).listeners.get('click')();
  assert.equal(h.fetchCalls.filter(([, options]) => options?.method === 'POST').length, 1);
  assert.ok(h.fetchCalls.some(([url]) => String(url).endsWith('/preparation/' + postedId)));
});

test('R4: failed preparation without retry permission remains disabled; completed operation opens only server-admitted AS', async () => {
  const h = createInterviewHarness();
  h.subject.renderProductRuntime(between(h, { operation_id: 'operation-a', status: 'failed', retry_allowed: false }));
  assert.equal(button(h).disabled, true);
  h.storage.clear();
  const saved = between(h, { operation_id: 'operation-b', status: 'running' }); h.subject.renderProductRuntime(saved);
  h.context.waitForProductCyclePreparation = waitForProductCyclePreparation;
  h.setFetch(async (url, options) => {
    assert.notEqual(options?.method, 'POST');
    if (String(url).includes('/preparation/')) return json({ operation_id: 'operation-b', status: 'completed', result: { decision: { status: 'SELECTED' } } });
    if (String(url).endsWith('/return-state')) return json({ cycle_id: 'cycle-a', allowed_action: 'connected' });
    return json({ ...h.snapshot(), current_situation: { ...h.snapshot().current_situation, status: 'admitted' } });
  });
  await button(h).listeners.get('click')();
  assert.equal(h.controls.textarea.disabled, true, 'admitted is not automatically started');
  assert.equal(h.fetchCalls.some(([url]) => /\/start$|\/prepare$/.test(url)), false);
});

test('R2: confirmed trace, AS phase and preparation progress never roll back', async () => {
  const h = createInterviewHarness(); h.subject.renderProductRuntime(h.snapshot(3));
  runtimeFetch(h, () => json(h.snapshot(2))); await h.subject.loadProductRuntime(); assert.equal(h.messages.children.length, 4);
  const ended = h.snapshot(3); ended.current_situation.status = 'scenario_ended'; h.subject.renderProductRuntime(ended);
  runtimeFetch(h, () => json(h.snapshot(3))); const saved = await h.subject.loadProductRuntime(); assert.equal(saved.current_situation.status, 'scenario_ended');
  h.context.known = between(h, { operation_id: 'op', status: 'running', preparation: { read_at: '2026-11-17T12:00:02Z' } });
  h.context.incoming = between(h, { operation_id: 'op', status: 'queued', preparation: { read_at: '2026-11-17T12:00:01Z' } });
  assert.equal(vm.runInContext('olderProductRuntimeSnapshot(incoming, known)', h.context), true);
  h.context.incoming.preparation_operation.preparation.read_at = '2026-11-17T12:00:03Z';
  assert.equal(vm.runInContext('olderProductRuntimeSnapshot(incoming, known)', h.context), false, 'newer worker requeue is valid');
});

for (const [collection, blocking, paused] of [['paused', false, true], ['paused', null, true], ['active', true, true], ['active', false, false], ['active', null, false]]) {
  test(`R6/R7: time mode ${collection}/${blocking} is independent of known budget`, () => {
    const h = createInterviewHarness({ timer: true }); const saved = between(h);
    saved.status.collection_status = collection; saved.blocking_system_wait = blocking;
    h.subject.renderProductRuntime(saved);
    assert.equal(h.context.interviewTimerBadge.classList.contains('is-paused'), paused);
    assert.match(h.context.interviewTimerBadge.textContent, /120:00/);
    assert.match(h.messages.querySelector('.preparation-time-notice').textContent, paused ? /Время на ответы сейчас не расходуется/ : /Сведения о времени сейчас недоступны/);
    assert.equal(saved.blocking_system_wait, blocking, 'renderer does not fabricate blocking wait');
  });
}
for (const value of [undefined, null, -1, '120', NaN, Infinity]) test(`R7: invalid remainder ${value} stays unknown and recovers after GET failure`, async () => {
  const h = createInterviewHarness({ timer: true }); const saved = between(h); saved.status.remaining_seconds = value;
  h.subject.renderProductRuntime(saved); assert.equal(h.context.interviewTimerBadge.textContent, 'Время недоступно');
  assert.equal(h.context.interviewTimerBadge.classList.contains('is-low-time'), false);
  runtimeFetch(h, () => { throw new TypeError('offline'); }); await assert.rejects(h.subject.loadProductRuntime());
  assert.equal(h.state.assessmentRemainingSeconds, null);
  assert.match(h.messages.querySelector('.preparation-time-notice').textContent, /Сведения о времени сейчас недоступны/);
  runtimeFetch(h, () => json(between(h))); await h.subject.loadProductRuntime(); assert.match(h.context.interviewTimerBadge.textContent, /120:00/);
});

test('R3/R5: old pending Next and detached handler cannot lock or mutate a new identity context', async () => {
  const h = createInterviewHarness(); h.subject.renderProductRuntime(between(h));
  h.context.waitForProductCyclePreparation = (accepted, options) => waitForProductCyclePreparation(accepted, { ...options, maxWaitMs: 0 });
  const old = deferred(), fresh = deferred(); let operationId;
  h.setFetch(async (_url, options) => {
    if (options?.method === 'POST') { operationId = JSON.parse(options.body).idempotency_key; return old.promise; }
    return fresh.promise;
  });
  const oldButton = button(h), priorClick = oldButton.listeners.get('click')(); await tick();
  h.state.identityEpoch++;
  h.subject.renderProductRuntime(between(h, { operation_id: operationId, status: 'queued' }));
  const freshButton = button(h); assert.equal(freshButton.disabled, false);
  await oldButton.listeners.get('click')(); assert.equal(h.fetchCalls.length, 1, 'detached handler makes no request');
  const freshClick = freshButton.listeners.get('click')(); await tick(); assert.equal(freshButton.disabled, true);
  old.reject(new TypeError('old offline')); await priorClick;
  assert.equal(freshButton.disabled, true, 'old completion does not release the new request');
  fresh.resolve(json({ operation_id: operationId, status: 'running' })); await freshClick;
  assert.equal(freshButton.disabled, false);
  assert.equal(h.fetchCalls.filter(([, options]) => options?.method === 'POST').length, 1);
});


test('R3: known Next refusal survives replacement; checks remain read-only', async () => {
  const h = createInterviewHarness(); const saved = between(h); h.subject.renderProductRuntime(saved);
  h.setFetch(async (url, options) => {
    if (options?.method === 'POST') return new Response('{}', { status: 409 });
    if (String(url).endsWith('/return-state')) return json({ cycle_id: 'cycle-a', allowed_action: 'connected' });
    return json(saved);
  });
  await button(h).listeners.get('click')();
  for (let poll = 0; poll < 2; poll++) {
    h.subject.renderProductRuntime(saved);
    assert.equal(button(h).disabled, false);
    await button(h).listeners.get('click')();
  }
  assert.equal(h.fetchCalls.filter(([, options]) => options?.method === 'POST').length, 1);
  assert.equal(h.fetchCalls.filter(([url]) => String(url).endsWith('/runtime')).length, 2);
});
