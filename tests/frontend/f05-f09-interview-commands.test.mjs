import assert from 'node:assert/strict';
import test from 'node:test';
import { createInterviewHarness } from './helpers/exec01-lifecycle-harness.mjs';

const json = (value, status = 200) => new Response(JSON.stringify(value), {
  status, headers: { 'Content-Type': 'application/json' },
});
const commandKey = (kind, situation = 'as-a') =>
  `agent4k.assessmentCommand:${kind}:cycle-a:${situation}:8`;

test('F07 a 409 is a refusal only after the exact status confirms absence', async () => {
  const h = createInterviewHarness();
  const snapshot = h.snapshot();
  h.subject.renderProductRuntime(snapshot); h.flush();
  h.setFetch(async (url, options) => {
    if (options?.method === 'POST') return json({ detail: 'M5_STATE_REVISION_CONFLICT' }, 409);
    if (String(url).endsWith('/runtime')) return json(snapshot);
    if (String(url).endsWith('/return-state')) return json({ cycle_id: 'cycle-a', allowed_action: 'none' });
    const params = new URL(url, 'https://example.test').searchParams;
    return json({ status: 'absent', cycle_id: 'cycle-a', assessment_situation_id: 'as-a',
      request_id: params.get('request_id'), turn_id: params.get('turn_id'), clarification_id: null });
  });
  await h.subject.sendProductInterviewAnswer('Синтетический ответ');
  const pending = h.subject.readProductInterviewAnswer();
  assert.equal(pending.status, 'rejected');
  assert.equal(pending.rejectionConfirmed, true);
  assert.match(h.errors.at(-1), /Ошибка отправки/);
  assert.equal(h.messages.children.some(item => item.dataset.pendingTurnId), false);
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

const boundary = (h, operation) => ({ ...h.snapshot(), current_situation: null, between_situations: true,
  participant_progress: { planned_total: 2, last_completed_position_no: 1 },
  route: { positions: [{ position_no: 1, state: 'completed', current_assessment_situation_id: 'as-a' }] },
  preparation_operation: operation });

test('F09 lost preparation receipt reads the original operation and keeps opening explicit', async () => {
  const h = createInterviewHarness();
  const snapshot = boundary(h);
  h.subject.renderProductRuntime(snapshot, { fresh: false });
  const operation = { operation_id: 'next:as-a', status: 'completed' };
  const next = { assessment_situation_id: 'next-admitted', expected_plan_revision_id: 'plan-2' };
  const ready = { ...boundary(h, operation), next_presentation: next };
  h.setFetch(async (url, options) => {
    if (String(url).endsWith('/next')) {
      assert.deepEqual(JSON.parse(options.body), { idempotency_key: operation.operation_id, after_assessment_situation_id: 'as-a' });
      throw new TypeError('lost receipt');
    }
    if (String(url).includes('/preparation/')) {
      assert.ok(String(url).endsWith('/preparation/next%3Aas-a'));
      return json(operation);
    }
    if (String(url).endsWith('/return-state')) return json({ cycle_id: 'cycle-a', allowed_action: 'connected' });
    if (String(url).endsWith('/runtime')) return json(ready);
    throw new Error('Unexpected request ' + url);
  });
  await h.messages.querySelector('.next-situation-button').listeners.get('click')();
  assert.equal(h.fetchCalls.filter(([, options]) => options?.method === 'POST').length, 1);
  assert.equal(h.messages.querySelector('.next-situation-button').textContent, 'Приступить к следующей ситуации');
  assert.equal(h.controls.textarea.disabled, true);
  assert.equal(h.storage.has(commandKey('next')), false);
});

test('F09 rejected enqueue stays read-only and never opens a different situation', async () => {
  const h = createInterviewHarness();
  const saved = boundary(h);
  h.subject.renderProductRuntime(saved, { fresh: false });
  h.setFetch(async (url, options) => {
    if (options?.method === 'POST') return json({ detail: 'M7_COLLECTION_CLOSED' }, 409);
    if (String(url).endsWith('/return-state')) return json({ cycle_id: 'cycle-a', allowed_action: 'connected' });
    if (String(url).endsWith('/runtime')) return json(saved);
    throw new Error('Unexpected request ' + url);
  });
  const click = () => h.messages.querySelector('.next-situation-button').listeners.get('click')();
  await click();
  assert.match(h.messages.querySelector('[data-next-preparation-feedback]').textContent, /отклонил|завершён/);
  await click();
  assert.equal(h.fetchCalls.filter(([, options]) => options?.method === 'POST').length, 1);
});

test('AC3 confirmed operation supersedes terminal refusal and exposes a read-only check', async () => {
  const h = createInterviewHarness();
  h.subject.renderProductRuntime(boundary(h, { operation_id: 'old', status: 'failed',
    error: { message: 'Старая безопасная причина.' } }));
  assert.equal(h.messages.querySelector('.next-situation-button'), null);
  const running = { operation_id: 'confirmed-new', status: 'running' };
  h.subject.renderProductRuntime(boundary(h, running));
  const card = h.messages.querySelector('.interview-next-card');
  assert.equal(card.querySelector('.interview-next-status').children[0].textContent, 'Готовим следующую ситуацию.');
  h.setFetch(async (url, options) => {
    assert.notEqual(options?.method, 'POST');
    if (String(url).endsWith('/return-state')) return json({ cycle_id: 'cycle-a', allowed_action: 'connected' });
    if (String(url).endsWith('/runtime')) return json(boundary(h, running));
    assert.ok(String(url).endsWith('/preparation/confirmed-new'));
    return json(running);
  });
  await card.querySelector('.next-situation-button').listeners.get('click')();
  assert.equal(h.fetchCalls.length, 3);
});

test('AC4 legacy failed operation without details retains safe fallback and hides the action', () => {
  const h = createInterviewHarness();
  h.subject.renderProductRuntime(boundary(h, { operation_id: 'legacy-failed', status: 'failed', retry_allowed: false }));
  const status = h.messages.querySelector('.interview-next-status');
  assert.equal(status.children[0].textContent, 'Следующая ситуация не открылась.');
  assert.match(status.children[1].textContent, /Не удалось подготовить следующую ситуацию/);
  assert.equal(h.messages.querySelector('.next-situation-button'), null);
  assert.equal(h.fetchCalls.length, 0);
});
