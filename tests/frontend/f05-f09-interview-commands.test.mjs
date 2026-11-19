import assert from 'node:assert/strict';
import test from 'node:test';
import { createInterviewHarness } from './helpers/exec01-lifecycle-harness.mjs';

const json = (value, status = 200) => new Response(JSON.stringify(value), {
  status, headers: { 'Content-Type': 'application/json' },
});
const commandKey = (kind, situation = 'as-a') =>
  `agent4k.assessmentCommand:${kind}:cycle-a:${situation}:8`;

test('F07 first known 409 is rejected beside the answer and a status check does not resend the Turn', async () => {
  const h = createInterviewHarness();
  const snapshot = h.snapshot();
  h.subject.renderProductRuntime(snapshot); h.flush();
  h.setFetch(async (url, options) => {
    if (options?.method === 'POST') return json({ detail: 'M5_AS_NOT_ACTIVE' }, 409);
    if (String(url).endsWith('/runtime')) return json(snapshot);
    return json({ status: 'absent', cycle_id: 'cycle-a', assessment_situation_id: 'as-a',
      request_id: h.subject.readProductInterviewAnswer()?.requestId,
      turn_id: h.subject.readProductInterviewAnswer()?.turnId, clarification_id: null });
  });
  await h.subject.sendProductInterviewAnswer('Синтетический ответ');
  const pending = h.subject.readProductInterviewAnswer();
  assert.equal(pending.status, 'rejected');
  assert.match(pending.rejectionMessage, /отклон|недоступ/);
  const row = h.messages.children.find((item) => item.dataset.pendingTurnId === pending.turnId);
  assert.match(row.querySelector('.interview-message-delivery-status').textContent, /отклон|недоступ/);
  assert.equal(h.fetchCalls.filter(([, options]) => options?.method === 'POST').length, 1);
  row.querySelector('.interview-message-retry').onclick();
  await Promise.resolve(); await Promise.resolve();
  assert.equal(h.fetchCalls.filter(([, options]) => options?.method === 'POST').length, 1);
  assert.equal(h.controls.submit.disabled, true);
});

test('F08 lost scenario_end response retains command identity and locks input through reload', async () => {
  const h = createInterviewHarness();
  const snapshot = h.snapshot(2);
  h.subject.renderProductRuntime(snapshot); h.flush();
  h.setFetch(async (url) => {
    if (String(url).endsWith('/return-state')) return json({ cycle_id: 'cycle-a', allowed_action: 'none' });
    if (String(url).endsWith('/runtime')) return json(snapshot);
    if (String(url).endsWith('/transitions')) throw new TypeError('lost response');
    throw new Error('Unexpected request');
  });
  await h.subject.finishProductAssessment();
  const saved = JSON.parse(h.storage.get(commandKey('scenario_end')));
  assert.ok(saved.operationId);
  assert.equal(h.fetchCalls.filter(([url]) => String(url).endsWith('/transitions')).length, 1);
  h.subject.renderProductRuntime(snapshot);
  assert.equal(h.controls.submit.disabled, true);
  assert.equal(h.controls.finish.disabled, true);
  assert.match(h.errors.at(-1), /Итог завершения|Проверяем уточнение/);
  const ended = { ...snapshot, current_situation: { ...snapshot.current_situation, status: 'scenario_ended' },
    clarification: { status: 'ASK', id: 'ask-a' } };
  h.subject.renderProductRuntime(ended);
  assert.equal(h.storage.has(commandKey('scenario_end')), false);
});

test('F09 lost Next response and reload check the saved operation without a second POST', async () => {
  const h = createInterviewHarness();
  const snapshot = { ...h.snapshot(), current_situation: null, between_situations: true };
  h.subject.renderProductRuntime(snapshot);
  const card = h.messages.children.find((item) => item.className === 'interview-return-card');
  const button = card.children.find((item) => item.className.split(' ').includes('primary-button'));
  h.setFetch(async (_url, options) => {
    if (options?.method === 'POST') throw new TypeError('lost response');
    return json({ operation_id: JSON.parse(h.storage.get(commandKey('next', 'between'))).operationId,
      status: 'queued' });
  });
  h.context.waitForProductCyclePreparation = async (operation) => {
    throw Object.assign(new Error('client wait ended'), { name: 'PreparationWaitLimit', operationId: operation.operation_id });
  };
  await button.listeners.get('click')();
  const saved = JSON.parse(h.storage.get(commandKey('next', 'between')));
  assert.ok(saved.operationId);
  assert.equal(h.fetchCalls.filter(([, options]) => options?.method === 'POST').length, 1);
  await button.listeners.get('click')();
  assert.equal(h.fetchCalls.filter(([, options]) => options?.method === 'POST').length, 1);
  assert.ok(h.fetchCalls.some(([url]) => String(url).includes('/cycles/preparation/' + saved.operationId)));
  h.subject.renderProductRuntime(snapshot);
  const restored = h.messages.children.find((item) => item.className === 'interview-return-card');
  assert.equal(restored.children.find((item) => item.className.split(' ').includes('primary-button')).textContent, 'Проверить состояние');
});

test('F09 server-opened next AS retires the old between-situations command', () => {
  const h = createInterviewHarness();
  const between = { ...h.snapshot(), current_situation: null, between_situations: true };
  h.subject.renderProductRuntime(between);
  h.storage.set(commandKey('next', 'between'), JSON.stringify({ cycleId: 'cycle-a',
    situationId: null, ownerId: '8', operationId: 'old-next' }));
  h.subject.renderProductRuntime(h.snapshot());
  assert.equal(h.storage.has(commandKey('next', 'between')), false);
  h.subject.renderProductRuntime(between);
  const card = h.messages.children.find((item) => item.className === 'interview-return-card');
  assert.equal(card.children.find((item) => item.className.split(' ').includes('primary-button')).textContent,
    'Приступить к следующей ситуации');
});

test('F09 known Next refusal makes the next click a readback rather than a new POST', async () => {
  const h = createInterviewHarness();
  const between = { ...h.snapshot(), current_situation: null, between_situations: true };
  h.subject.renderProductRuntime(between);
  const card = h.messages.children.find((item) => item.className === 'interview-return-card');
  const button = card.children.find((item) => item.className.split(' ').includes('primary-button'));
  h.setFetch(async (url, options) => {
    if (options?.method === 'POST') return json({ detail: 'M7_COLLECTION_CLOSED' }, 409);
    if (String(url).endsWith('/return-state')) return json({ cycle_id: 'cycle-a', allowed_action: 'none' });
    if (String(url).endsWith('/runtime')) return json(between);
    throw new Error('Unexpected request');
  });
  await button.listeners.get('click')();
  assert.equal(h.fetchCalls.filter(([, options]) => options?.method === 'POST').length, 1);
  assert.match(card.children.at(-1).textContent, /отклонил|завершён/);
  await button.listeners.get('click')();
  assert.equal(h.fetchCalls.filter(([, options]) => options?.method === 'POST').length, 1);
});

test('AC3 confirmed replacement operation supersedes a stored Next receipt and clears the old reason', async () => {
  const h = createInterviewHarness();
  const between = { ...h.snapshot(), current_situation: null, between_situations: true };
  h.subject.renderProductRuntime({ ...between, preparation_operation: {
    operation_id: 'refused-old', status: 'failed', retry_allowed: false,
    error: { message: 'Старая безопасная причина.' },
  } });
  assert.match(h.messages.children[0].children.at(-1).textContent, /Старая безопасная причина/);
  h.subject.renderProductRuntime({ ...between, preparation_operation: { operation_id: 'confirmed-new', status: 'running' } });
  const card = h.messages.children[0], button = card.querySelector('.next-situation-button');
  assert.equal(card.children.at(-1).textContent.includes('Старая безопасная причина'), false);
  assert.equal(button.disabled, false);
  h.setFetch(async url => {
    assert.equal(url, '/users/assessment/cycles/preparation/confirmed-new');
    return json({ operation_id: 'confirmed-new', status: 'running' });
  });
  h.context.waitForProductCyclePreparation = async () => {
    throw Object.assign(new Error('wait ended'), { name: 'PreparationWaitLimit' });
  };
  await button.listeners.get('click')();
  assert.equal(h.fetchCalls.length, 1);
  assert.equal(h.fetchCalls.filter(([, options]) => options?.method === 'POST').length, 0);
  assert.equal(JSON.parse(h.storage.get(commandKey('next', 'between'))).operationId, 'confirmed-new');
});

test('AC4 legacy failed operation without details retains safe fallback and denies a new Next', () => {
  const h = createInterviewHarness();
  h.subject.renderProductRuntime({ ...h.snapshot(), current_situation: null, between_situations: true,
    preparation_operation: { operation_id: 'legacy-failed', status: 'failed', retry_allowed: false } });
  const card = h.messages.children[0];
  assert.equal(card.children.at(-1).textContent, 'Не удалось подготовить следующую ситуацию.');
  assert.equal(card.querySelector('.next-situation-button').disabled, true);
  assert.equal(h.fetchCalls.length, 0);
});
