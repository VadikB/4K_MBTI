import test from 'node:test';
import assert from 'node:assert/strict';
import { preparationText, preparationCopy, preparationHtml } from '../../web/js/preparation-status.js';
const now = Date.parse('2026-11-16T12:00:00Z');
const model = { kind: 'assessment', status: 'running', stage_label: 'Проверяем материалы ситуации',
  explanation: 'Проверяем, что ситуацию можно открыть для прохождения.',
  started_at: '2026-11-16T11:30:00Z', stage_started_at: '2026-11-16T11:33:00Z',
  last_progress_at: '2026-11-16T11:33:00Z', read_at: '2026-11-16T12:00:00Z',
  freshness: 'confirmed', delayed: true, delay_notice_seconds: 300, reference: 'P4K-1234567890ABCDEF12345678' };
test('30 minute wait uses saved times and contains only human support information', () => {
  const copy = preparationCopy(model, { now });
  assert.match(copy, /30 мин/); assert.match(copy, /27 мин/); assert.match(copy, /P4K-/);
  assert.doesNotMatch(copy, /operation_id|attempt_token|JSON|SQL|модель|заявка/);
  assert.match(preparationText(model, { now, readError: true }), /последние полученные/);
});
test('failed and completed win over delay; stale heartbeat does not claim working', () => {
  assert.doesNotMatch(preparationText({ ...model, status: 'completed' }, { now }), /больше времени/);
  assert.doesNotMatch(preparationText({ ...model, status: 'failed' }, { now }), /больше времени/);
  assert.match(preparationText({ ...model, freshness: 'unconfirmed' }, { now }), /не можем подтвердить/);
});
test('markup escapes server text and has no live timer or fixed technical stepper', () => {
  assert.doesNotMatch(preparationHtml({ ...model, stage_label: '<script>' }), /<script>/);
  assert.doesNotMatch(preparationHtml(model), /aria-live|progressbar|из 5/);
});

test('delay threshold is exactly five minutes and terminal elapsed time stops', () => {
  const initial={...model,delayed:false,stage_started_at:'2026-11-16T11:55:00Z'};
  assert.doesNotMatch(preparationText(initial,{now:now-1}),/больше времени/);
  assert.match(preparationText(initial,{now}),/больше времени/);
  const finished={...model,status:'completed',finished_at:'2026-11-16T12:00:00Z'};
  assert.equal(preparationText(finished,{now}),preparationText(finished,{now:now+600000}));
});
