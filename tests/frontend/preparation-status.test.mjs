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

test('read failure and success describe reading, never an answer receipt', () => {
  const failedRead = preparationText(model, { now, readError: true });
  assert.match(failedRead, /Последний известный этап:/);
  assert.match(failedRead, /Не удалось обновить состояние. Показаны последние полученные сведения/);
  assert.doesNotMatch(failedRead, /не подтверждено|соединение|Сейчас:|больше времени/);
  const success = preparationText(model, { now });
  assert.doesNotMatch(success, /Не удалось обновить|Последний известный/);
  assert.match(success, /Подготовка: 30 мин · Этап без изменений: 27 мин/);
});
test('stale or unconfirmed data freeze durations at the successful read', () => {
  for (const options of [{ readError:true, now:now+600000 }, { now:now+600000 }]) {
    const text=preparationText(model, options);
    assert.match(text, /Подготовка: 30 мин · Этап без изменений: 27 мин \(на момент обновления\)/);
    assert.doesNotMatch(text, /40 мин|Сейчас:/);
  }
  const text=preparationText({...model, freshness:'unconfirmed'}, {now:now+60000});
  assert.match(text, /Сейчас не можем подтвердить, что подготовка продолжается/);
  assert.match(text, /Подготовка: 30 мин/);
  assert.doesNotMatch(text, /соединение|больше времени/);
});
test('confirmed failure and failed read remain two separate facts', () => {
  const text=preparationText({...model,status:'failed'}, {now,readError:true});
  assert.match(text, /Не удалось завершить подготовку оценки/);
  assert.match(text, /Не удалось обновить состояние/);
  assert.doesNotMatch(text, /больше времени|продолжается/);
});
test('one stage, disclosed number and complete human details in compact markup', () => {
  const html=preparationHtml(model,{compact:true});
  assert.match(html,/preparation-status--compact/);
  assert.doesNotMatch(html, /<details open|Сведения скопированы|Код обращения/);
  assert.ok(html.indexOf('Номер подготовки')>html.indexOf('<details>'));
  assert.match(html,/Поможет найти эту подготовку при разборе задержки или ошибки/);
  assert.equal(preparationText(model,{now}).split(model.stage_label).length-1,1);
  assert.match(preparationCopy(model,{now}),/Сведения обновлены:/);
});


test('public Next failure reason replaces generic failure, including after a failed GET', () => {
  const failed = { ...model, kind: 'next', status: 'failed',
    explanation: 'Не удалось завершить подготовку. Проверяем материалы ситуации.' };
  const failureMessage = 'Материалы ситуации не прошли обязательную проверку. Обратитесь к организатору оценки.';
  for (const readError of [false, true]) {
    const text = preparationText(failed, { now, failureMessage, readError });
    assert.equal(text.split(failureMessage).length - 1, 1);
    assert.doesNotMatch(text, /Не удалось завершить/);
    assert.equal(text.includes('Не удалось обновить состояние'), readError);
  }
  assert.match(preparationText(failed, { now }), /Не удалось завершить подготовку/);
  assert.doesNotMatch(preparationText(model, { now, failureMessage }), /не прошли обязательную/);
});
