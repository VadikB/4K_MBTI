import assert from 'node:assert/strict';
import fs from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';
import { createInterviewHarness } from './helpers/p3-a-interview.mjs';

const json = (value, status = 200) => new Response(JSON.stringify(value), {
  status, headers: { 'Content-Type': 'application/json' },
});
const deferred = () => {
  let resolve; let reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
};
const tick = async () => { for (let i = 0; i < 20; i += 1) await Promise.resolve(); };
const setup = (options) => {
  const h = createInterviewHarness(options);
  h.runtime = h.snapshot();
  h.subject.renderProductRuntime(h.runtime);
  h.flush();
  return h;
};
const draft = (h, raw) => {
  h.textarea.value = raw;
  h.storage.set(`agent4k.assessmentDraft:${h.state.productCycleId}:${h.state.productAssessmentSituationId}`, raw);
};
const postCalls = (h) => h.fetchCalls.filter(([, options]) => options?.method === 'POST');
const addTurn = (runtime, body) => {
  const turn = { turn_id: body.turn_id, request_id: body.request_id,
    speaker_type: 'assessee', content_text: body.content, sequence_no: 1 };
  if (!runtime.trace.turns.some((saved) => saved.turn_id === turn.turn_id)) runtime.trace.turns.push(turn);
  return turn;
};
const pendingKeys = (h) => [...h.storage.keys()].filter((key) => key.startsWith('agent4k.assessmentPending:'));
const pendingRow = (h) => h.messages.children.find((row) => row.dataset.pendingTurnId);
const deliveryText = (row) => row?.querySelector('.interview-message-delivery-status')?.textContent;

test('P3-A HTML and synchronous Cycle entry keep input/actions disabled until confirmed runtime', async () => {
  const html = fs.readFileSync(new URL('../../web/index.html', import.meta.url), 'utf8');
  for (const id of ['interview-textarea', 'interview-submit-button', 'interview-finish-button']) {
    const tag = html.match(new RegExp('<(?:textarea|button)\\b[^>]*\\bid="' + id + '"[^>]*>'))?.[0];
    assert.ok(tag, `entry control ${id} exists`);
    assert.match(tag, /\bdisabled(?:\s|=|>)/, `${id} is unavailable before JS/runtime`);
  }
  for (const paused of [false, true]) {
    const h = createInterviewHarness(); h.state.productAssessmentSituationId = 'as-a';
    const raw = '  Существующий черновик\nс новой строкой  '; draft(h, raw);
    h.controls.textarea.disabled = false; h.controls.submit.disabled = false; h.controls.finish.disabled = false;
    const held = deferred();
    h.context.loadProductRuntime = () => held.promise.then((runtime) => h.subject.renderProductRuntime(runtime));
    h.subject.openInterview();
    assert.equal(h.controls.textarea.disabled, true);
    assert.equal(h.controls.submit.disabled, true);
    assert.equal(h.controls.finish.disabled, true);
    assert.equal(h.textarea.value, raw);
    assert.equal(h.storage.get('agent4k.assessmentDraft:cycle-a:as-a'), raw);
    const runtime = h.snapshot(); if (paused) runtime.status.collection_status = 'paused';
    held.resolve(runtime); await tick();
    assert.equal(h.controls.textarea.disabled, paused);
    assert.equal(h.controls.submit.disabled, paused);
    assert.equal(h.controls.finish.disabled, paused);
    assert.equal(h.textarea.value, raw);
  }
});

test('P3-A late preflight cannot post or mutate a different Cycle/AS/screen/owner/epoch', async () => {
  for (const change of [
    (h) => { h.subject.renderProductRuntime(h.snapshot(0, 'as-b', 'cycle-b')); },
    (h) => { h.subject.renderProductRuntime(h.snapshot(0, 'as-b')); },
    (h) => { h.state.currentScreen = 'prechat'; },
    (h) => { h.state.pendingUser = { id: 9 }; },
    (h) => { h.state.identityEpoch += 1; },
  ]) {
    const h = setup(); draft(h, '  Ответ A\nвторая строка  ');
    const held = deferred(); h.setFetch(() => held.promise);
    const sending = h.subject.sendProductInterviewAnswer(h.textarea.value.trim());
    change(h); draft(h, 'Новый черновик');
    const currentNode = h.messages.firstChild;
    const currentErrorCount = h.errors.length;
    held.resolve(json(h.runtime));
    await sending;
    assert.equal(postCalls(h).length, 0);
    assert.equal(h.textarea.value, 'Новый черновик');
    assert.equal(h.messages.firstChild, currentNode);
    assert.equal(h.errors.length, currentErrorCount);
    assert.equal(h.textarea.focused, undefined);
  }
});

test('P3-A known POST receipt survives failed readback/reload and is never resent', async () => {
  const h = setup(); const raw = '  Первая строка\nВторая строка  '; draft(h, raw);
  let gets = 0; let savedTurn;
  h.setFetch(async (_url, options) => {
    if (options?.method === 'POST') {
      savedTurn = addTurn(h.runtime, JSON.parse(options.body)); return json({ turn: savedTurn });
    }
    gets += 1;
    return gets === 1 ? json(h.runtime) : json({}, 503);
  });
  const result = await h.subject.sendProductInterviewAnswer(raw.trim());
  assert.equal(result.accepted, true);
  assert.equal(result.pending, true);
  assert.equal(h.textarea.value, '');
  assert.equal(h.storage.has('agent4k.assessmentDraft:cycle-a:as-a'), false);
  assert.ok(deliveryText(pendingRow(h)).includes('Ответ принят'));
  assert.equal(h.controls.submit.disabled, true);
  const operation = h.subject.readProductInterviewAnswer();
  assert.equal(operation.accepted, true);
  const restored = setup({ storage: h.storage });
  restored.runtime.trace.turns = [savedTurn];
  restored.setFetch(async () => json(restored.runtime));
  await restored.subject.sendProductInterviewAnswer(raw.trim());
  assert.equal(postCalls(restored).length, 0);
  assert.equal(pendingKeys(restored).length, 0);
  assert.equal(restored.messages.children.filter((row) => row.dataset.turnId === operation.turnId).length, 1);
  assert.equal(pendingRow(restored), undefined);
});

test('P3-A commit then lost response retains one identity across reload and same-key provider recovery', async () => {
  const h = setup(); const raw = 'Неизвестный исход\nс сохранённым Turn'; draft(h, raw);
  h.setFetch(async (_url, options) => {
    if (!options?.method) return json(h.runtime);
    addTurn(h.runtime, JSON.parse(options.body)); throw new TypeError('Failed to fetch');
  });
  await h.subject.sendProductInterviewAnswer(raw);
  const original = h.subject.readProductInterviewAnswer();
  assert.equal(original.accepted, false);
  assert.equal(h.controls.submit.disabled, true);
  const restored = setup({ storage: h.storage });
  restored.subject.renderProductRuntime(h.runtime);
  const saved = restored.subject.readProductInterviewAnswer();
  assert.equal(saved.status, 'saved');
  assert.equal(saved.turnId, original.turnId);
  assert.equal(pendingRow(restored), undefined, 'the saved Turn replaces its local unknown row');
  assert.equal(restored.storage.has('agent4k.assessmentDraft:cycle-a:as-a'), false);
  restored.setFetch(async (_url, options) => {
    if (_url.includes('/answer-status?')) return json({ status: 'accepted', processing_status: 'failed',
      cycle_id: original.cycleId, assessment_situation_id: original.situationId, request_id: original.requestId,
      turn_id: original.turnId, clarification_id: null, turn: h.runtime.trace.turns[0] });
    if (!options?.method) return json(h.runtime);
    const body = JSON.parse(options.body);
    assert.equal(body.request_id, original.requestId);
    assert.equal(body.turn_id, original.turnId);
    return json({ turn: addTurn(h.runtime, body), idempotent: true });
  });
  await restored.subject.sendProductInterviewAnswer(raw);
  assert.equal(postCalls(restored).length, 1);
  assert.equal(h.runtime.trace.turns.length, 1);
  assert.equal(pendingKeys(restored).length, 0);
  assert.equal(restored.messages.children.filter((row) => row.dataset.turnId === original.turnId).length, 1);
  assert.equal(deliveryText(restored.messages.children.find((row) => row.dataset.turnId === original.turnId)), '',
    'successful same-key recovery clears the saved/processing delivery on an unchanged history DOM');
});

test('P3-A failed readback never establishes absence or permits a fresh blind command', async () => {
  const h = setup(); draft(h, 'Исходный ответ');
  h.setFetch(async (_url, options) => {
    if (options?.method) throw new Error('lost response');
    return json(h.runtime);
  });
  await h.subject.sendProductInterviewAnswer('Исходный ответ');
  const original = h.subject.readProductInterviewAnswer();
  h.setFetch(async () => json({}, 503));
  draft(h, 'Изменённый черновик');
  await h.subject.sendProductInterviewAnswer('Изменённый черновик');
  await h.subject.sendProductInterviewAnswer('Исходный ответ');
  assert.equal(postCalls(h).length, 1, 'failed subsequent readback adds no new POST');
  assert.equal(h.subject.readProductInterviewAnswer().turnId, original.turnId);
  assert.equal(h.textarea.value, 'Изменённый черновик');
});

test('P3-A raw multiline draft changed during POST is not erased by an older acceptance', async () => {
  const h = setup(); const raw = '  Исходный ответ\nс пробелами  '; draft(h, raw);
  const held = deferred(); let body;
  h.setFetch(async (_url, options) => {
    if (!options?.method) return json(h.runtime);
    body = JSON.parse(options.body); return held.promise;
  });
  const sending = h.subject.sendProductInterviewAnswer(raw.trim()); await tick();
  draft(h, raw + '\nНовая строка');
  held.resolve(json({ turn: addTurn(h.runtime, body) }));
  await sending;
  assert.equal(h.textarea.value, raw + '\nНовая строка');
  assert.equal(h.storage.get('agent4k.assessmentDraft:cycle-a:as-a'), raw + '\nНовая строка');
});

test('P3-A late POST success/error stays in its original scope and cannot enable/focus another view', async () => {
  for (const accepted of [true, false]) {
    for (const change of [
      (h) => { h.subject.renderProductRuntime(h.snapshot(0, 'as-b', 'cycle-b')); },
      (h) => { h.state.currentScreen = 'prechat'; },
      (h) => { h.state.pendingUser = { id: 9 }; h.state.identityEpoch += 1; },
    ]) {
      const h = setup(); draft(h, 'Исходный ответ'); const held = deferred(); let body;
      h.setFetch(async (_url, options) => {
        if (!options?.method) return json(h.runtime);
        body = JSON.parse(options.body); return held.promise;
      });
      const sending = h.subject.sendProductInterviewAnswer('Исходный ответ'); await tick();
      change(h); draft(h, 'Новый черновик');
      const node = h.messages.firstChild; const errorCount = h.errors.length;
      const disabled = h.controls.submit.disabled;
      held.resolve(accepted ? json({ turn: addTurn(h.runtime, body) }) : json({}, 503));
      await sending;
      assert.equal(h.textarea.value, 'Новый черновик');
      assert.equal(h.messages.firstChild, node);
      assert.equal(h.errors.length, errorCount);
      assert.equal(h.controls.submit.disabled, disabled);
      assert.equal(h.textarea.focused, undefined);
      const old = JSON.parse(h.storage.get('agent4k.assessmentPending:cycle-a:as-a:8'));
      assert.equal(old.accepted, accepted);
      assert.equal(old.turnId, body.turn_id);
      assert.equal(h.pollingResumes(), 0);
    }
  }
});

test('P3-A a pause confirmed during POST remains authoritative after the old request fails', async () => {
  const h = setup(); draft(h, 'Ответ'); const held = deferred();
  h.setFetch(async (_url, options) => options?.method ? held.promise : json(h.runtime));
  const sending = h.subject.sendProductInterviewAnswer('Ответ'); await tick();
  const paused = h.snapshot(); paused.status.collection_status = 'paused';
  h.subject.renderProductRuntime(paused);
  held.resolve(json({}, 409)); await sending;
  assert.equal(h.controls.textarea.disabled, true);
  assert.equal(h.controls.submit.disabled, true);
  assert.equal(h.controls.finish.disabled, true);
  assert.equal(h.textarea.focused, undefined);
});

test('P3-A double retry shares one in-flight guard and preserves the pending row through history rebuild', async () => {
  const h = setup(); draft(h, 'Повторяемый ответ');
  h.setFetch(async (_url, options) => {
    if (options?.method) throw new Error('lost response');
    return json(h.runtime);
  });
  await h.subject.sendProductInterviewAnswer('Повторяемый ответ');
  const original = h.subject.readProductInterviewAnswer();
  const held = deferred(); h.fetchCalls.length = 0; h.setFetch(() => held.promise);
  const first = h.subject.sendProductInterviewAnswer('Повторяемый ответ');
  const second = await h.subject.sendProductInterviewAnswer('Повторяемый ответ');
  assert.equal(second.busy, true);
  h.subject.renderProductRuntime(h.snapshot(1));
  assert.equal(pendingRow(h)?.dataset.pendingTurnId, original.turnId);
  assert.equal(h.controls.submit.disabled, true);
  assert.equal(h.fetchCalls.length, 1);
  held.reject(new Error('offline')); await first;
  assert.equal(h.subject.readProductInterviewAnswer().turnId, original.turnId);
});

test('P3-A stale retained retry callback cannot turn an old answer into a new AS command', async () => {
  const h = setup(); draft(h, 'Ответ A');
  h.setFetch(async (_url, options) => {
    if (options?.method) throw new Error('lost response');
    return json(h.runtime);
  });
  await h.subject.sendProductInterviewAnswer('Ответ A');
  const oldRetry = pendingRow(h).querySelector('.interview-message-retry').onclick;
  h.subject.renderProductRuntime(h.snapshot(0, 'as-b')); draft(h, 'Черновик B');
  const reads = h.fetchCalls.length;
  oldRetry(); await tick();
  assert.equal(h.fetchCalls.length, reads);
  assert.equal(h.textarea.value, 'Черновик B');
  assert.equal(h.subject.readProductInterviewAnswer(), null);
});

test('P3-A a failed preflight sent nothing and leaves the draft editable for a corrected new answer', async () => {
  const h = setup(); draft(h, 'Старый черновик');
  h.setFetch(async () => json({}, 503));
  await h.subject.sendProductInterviewAnswer('Старый черновик');
  assert.equal(pendingKeys(h).length, 0);
  assert.equal(pendingRow(h), undefined);
  assert.equal(h.controls.submit.disabled, false);
  assert.equal(h.textarea.value, 'Старый черновик');
  draft(h, 'Исправленный ответ');
  h.setFetch(async (_url, options) => {
    if (!options?.method) return json(h.runtime);
    const body = JSON.parse(options.body);
    assert.equal(body.content, 'Исправленный ответ');
    return json({ turn: addTurn(h.runtime, body) });
  });
  await h.subject.sendProductInterviewAnswer('Исправленный ответ');
  assert.equal(postCalls(h).length, 1);
  assert.equal(h.runtime.trace.turns[0].content_text, 'Исправленный ответ');
});

test('P3-A reload during prepared preflight discards only the undispatched operation and keeps its draft', async () => {
  const h = setup(); draft(h, 'Черновик до перезагрузки\nвторая строка');
  h.subject.prepareProductInterviewAnswer(h.textarea.value, h.textarea.value);
  assert.equal(pendingKeys(h).length, 1);
  const restored = setup({ storage: h.storage });
  assert.equal(pendingKeys(restored).length, 0);
  assert.equal(pendingRow(restored), undefined);
  assert.equal(restored.textarea.value, 'Черновик до перезагрузки\nвторая строка');
  assert.equal(restored.controls.submit.disabled, false);
  assert.equal(restored.controls.textarea.disabled, false);
  draft(restored, 'Исправленный после reload');
  restored.setFetch(async (_url, options) => {
    if (!options?.method) return json(restored.runtime);
    const body = JSON.parse(options.body);
    assert.equal(body.content, 'Исправленный после reload');
    return json({ turn: addTurn(restored.runtime, body) });
  });
  await restored.subject.sendProductInterviewAnswer('Исправленный после reload');
  assert.equal(postCalls(restored).length, 1);
  assert.equal(restored.runtime.trace.turns.length, 1);
});

test('P3-A a retained retry callback cannot resurrect a resolved operation in the same AS', async () => {
  const h = setup(); draft(h, 'Первый ответ');
  h.setFetch(async (_url, options) => {
    if (options?.method) throw new Error('lost response');
    return json(h.runtime);
  });
  await h.subject.sendProductInterviewAnswer('Первый ответ');
  const original = h.subject.readProductInterviewAnswer();
  const oldRetry = pendingRow(h).querySelector('.interview-message-retry').onclick;
  h.setFetch(async (_url, options) => {
    if (_url.includes('/answer-status?')) return json({ status: 'absent', cycle_id: original.cycleId,
      assessment_situation_id: original.situationId, request_id: original.requestId, turn_id: original.turnId, clarification_id: null });
    if (!options?.method) return json(h.runtime);
    return json({ turn: addTurn(h.runtime, JSON.parse(options.body)) });
  });
  await h.subject.sendProductInterviewAnswer('Первый ответ');
  assert.equal(pendingKeys(h).length, 0);
  draft(h, 'Следующий черновик'); const calls = h.fetchCalls.length;
  oldRetry(); await tick();
  assert.equal(h.fetchCalls.length, calls);
  assert.equal(pendingKeys(h).length, 0);
  assert.equal(h.textarea.value, 'Следующий черновик');
});

test('P3-A paused/closed/unpresented clarification phases do not issue POST or enable their input', async () => {
  for (const change of [
    (runtime) => { runtime.status.collection_status = 'paused'; },
    (runtime) => { runtime.status.collection_status = 'collection_closed'; },
    (runtime) => { runtime.current_situation.status = 'scenario_ended'; },
    (runtime) => { runtime.current_situation.status = 'scenario_ended'; runtime.clarification = {
      id: '00000000-0000-4000-8000-000000000099', status: 'ASK', question: { text: 'Ещё вопрос' }, question_turn_id: null,
    }; },
  ]) {
    const h = setup(); change(h.runtime); h.subject.renderProductRuntime(h.runtime); draft(h, 'Сохранённый черновик');
    h.setFetch(async () => json(h.runtime)); await h.subject.sendProductInterviewAnswer('Сохранённый черновик');
    assert.equal(postCalls(h).length, 0);
    assert.equal(h.controls.textarea.disabled, true);
    assert.equal(h.controls.submit.disabled, true);
    assert.equal(h.textarea.value, 'Сохранённый черновик');
  }
});

test('P3-A source endpoint/clarification decision is never retargeted after phase changes', async () => {
  const h = setup();
  h.runtime.current_situation.status = 'scenario_ended';
  h.runtime.clarification = { id: '00000000-0000-4000-8000-000000000098', status: 'ASK',
    question_turn_id: '00000000-0000-4000-8000-000000000097', question: { text: 'Первое уточнение' } };
  h.subject.renderProductRuntime(h.runtime); draft(h, 'Ответ на первое уточнение');
  h.setFetch(async (_url, options) => {
    if (options?.method) throw new Error('lost response');
    return json(h.runtime);
  });
  await h.subject.sendProductInterviewAnswer(h.textarea.value);
  const original = h.subject.readProductInterviewAnswer();
  h.runtime.clarification.id = '00000000-0000-4000-8000-000000000096';
  h.setFetch(async () => json(h.runtime)); await h.subject.sendProductInterviewAnswer(h.textarea.value);
  assert.equal(postCalls(h).length, 1, 'the old unknown operation is not posted again into the new phase');
  assert.equal(h.subject.readProductInterviewAnswer().endpoint, original.endpoint);
  assert.equal(h.subject.readProductInterviewAnswer().clarificationId, original.clarificationId);
});

test('P3-A receipt validation distinguishes M5 turn and M7 answer; empty/foreign 2xx stays unknown', async () => {
  for (const receipt of [{}, { turn: { turn_id: 'foreign', speaker_type: 'assessee', content_text: 'Ответ' } }]) {
    const h = setup(); draft(h, 'Ответ');
    h.setFetch(async (_url, options) => json(options?.method ? receipt : h.runtime));
    const result = await h.subject.sendProductInterviewAnswer('Ответ');
    assert.equal(result.accepted, false);
    assert.equal(h.subject.readProductInterviewAnswer().accepted, false);
    assert.equal(h.textarea.value, 'Ответ');
    assert.ok(deliveryText(pendingRow(h)).includes('неизвестен'));
  }
  const h = setup();
  h.runtime.current_situation.status = 'scenario_ended';
  h.runtime.clarification = { id: '00000000-0000-4000-8000-000000000098', status: 'ASK',
    question_turn_id: '00000000-0000-4000-8000-000000000097', question: { text: 'Уточнение' } };
  h.subject.renderProductRuntime(h.runtime); draft(h, 'Ответ на уточнение');
  h.setFetch(async (url, options) => {
    if (!options?.method) return json(h.runtime);
    assert.ok(url.endsWith('/00000000-0000-4000-8000-000000000098/answers'));
    const body = JSON.parse(options.body); addTurn(h.runtime, body);
    return json({ id: h.runtime.clarification.id, answer_turn_id: body.turn_id,
      response_request_id: body.request_id, response_outcome: 'answered' });
  });
  const result = await h.subject.sendProductInterviewAnswer('Ответ на уточнение');
  assert.equal(result.accepted, true); assert.equal(result.verified, true);
  assert.equal(pendingKeys(h).length, 0); assert.equal(h.textarea.value, '');
});

test('P3-A a return/Continue card survives a pending GET error without cached AS resurrection', async () => {
  const h = setup(); draft(h, 'Ответ'); const held = deferred(); h.setFetch(() => held.promise);
  const sending = h.subject.sendProductInterviewAnswer('Ответ');
  h.messages.innerHTML = '';
  const card = h.context.document.createElement('section'); card.className = 'interview-return-card';
  h.messages.appendChild(card); h.controls.textarea.disabled = true; h.controls.submit.disabled = true;
  held.resolve(json({}, 409)); await sending;
  assert.equal(h.messages.firstChild, card);
  assert.equal(h.controls.textarea.disabled, true);
  assert.equal(postCalls(h).length, 0);
  assert.equal(h.pollingResumes(), 0);
});

test('P3-A malformed persisted operation and overlong new text never fetch or corrupt the editable draft', async () => {
  for (const mutate of [
    (op) => { op.turnId = {}; }, (op) => { op.requestId = []; },
    (op) => { op.endpoint = '/users/other'; }, (op) => { op.status = 'invented'; },
    (op) => { op.sourcePhase = '{}'; }, (op) => { op.ownerId = 'foreign'; },
    (op) => { op.clarificationId = '../../other'; },
  ]) {
    const h = setup(); draft(h, 'Черновик'); const op = h.subject.prepareProductInterviewAnswer('Черновик', 'Черновик');
    const key = pendingKeys(h)[0]; mutate(op); h.storage.set(key, JSON.stringify(op));
    await h.subject.sendProductInterviewAnswer('Черновик');
    assert.equal(h.fetchCalls.length, 0); assert.equal(h.textarea.value, 'Черновик');
  }
  const h = setup(); draft(h, 'a'.repeat(10001));
  await h.subject.sendProductInterviewAnswer(h.textarea.value);
  assert.equal(h.fetchCalls.length, 0); assert.equal(pendingKeys(h).length, 0);
  draft(h, 'Короткий ответ');
  h.setFetch(async (_url, options) => {
    if (!options?.method) return json(h.runtime);
    return json({ turn: addTurn(h.runtime, JSON.parse(options.body)) });
  });
  const sent = await h.subject.sendProductInterviewAnswer('Короткий ответ'); assert.equal(sent.verified, true);
});

test('P3-A UUID fallback uses secure random bytes and preserves the draft when crypto is unavailable', async () => {
  const h = setup(); draft(h, 'Ответ из браузера без randomUUID');
  let randomCalls = 0;
  h.context.crypto = { getRandomValues(bytes) { randomCalls += 1; bytes.fill(0xff); return bytes; } };
  const operation = h.subject.prepareProductInterviewAnswer(h.textarea.value, h.textarea.value);
  assert.equal(randomCalls, 1);
  assert.equal(operation.turnId, 'ffffffff-ffff-4fff-bfff-ffffffffffff');
  assert.match(operation.turnId, /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/);
  assert.equal(h.subject.readProductInterviewAnswer().turnId, operation.turnId);
  const unavailable = setup(); draft(unavailable, 'Сохранённый черновик');
  delete unavailable.context.crypto;
  await unavailable.subject.sendProductInterviewAnswer('Сохранённый черновик');
  assert.equal(unavailable.fetchCalls.length, 0);
  assert.equal(pendingKeys(unavailable).length, 0);
  assert.equal(unavailable.textarea.value, 'Сохранённый черновик');
  assert.ok(unavailable.errors.at(-1).includes('идентификатор'));
});

test('P3-A wiring captures scope/raw draft before lazy import and its old guard cannot block a new AS', async () => {
  const h = setup();
  const wiring = fs.readFileSync(new URL('../../web/js/wiring.js', import.meta.url), 'utf8');
  const start = wiring.indexOf('let failedInterviewMessage =');
  const end = wiring.indexOf("interviewForm.addEventListener('submit'");
  h.context.loadInterview = async () => h.subject;
  h.context.interviewSubmitLabel = { textContent: '' };
  vm.runInContext(wiring.slice(start, end) + '\nglobalThis.wiringSubject = {submitCurrentInterviewAnswer};', h.context);
  const heldA = deferred(); const heldB = deferred();
  h.setFetch((url) => url.includes('/cycle-a/') ? heldA.promise : heldB.promise);
  draft(h, 'Ответ A'); const sendingA = h.context.wiringSubject.submitCurrentInterviewAnswer(); await tick();
  h.subject.renderProductRuntime(h.snapshot(0, 'as-b', 'cycle-b')); draft(h, 'Ответ B');
  const sendingB = h.context.wiringSubject.submitCurrentInterviewAnswer(); await tick();
  assert.equal(h.fetchCalls.length, 2, 'a still pending A does not suppress a permitted B send');
  heldA.resolve(json(h.runtime)); await sendingA;
  assert.equal(h.textarea.value, 'Ответ B');
  assert.equal(h.context.interviewSubmitLabel.textContent, 'Отправляем...');
  heldB.reject(new Error('offline')); await sendingB;
  assert.equal(postCalls(h).length, 0);
});

test('P3-A wiring preserves the exact pre-import raw draft while a newer multiline draft is entered', async () => {
  const h = setup();
  const wiring = fs.readFileSync(new URL('../../web/js/wiring.js', import.meta.url), 'utf8');
  const heldImport = deferred(); h.context.loadInterview = () => heldImport.promise;
  h.context.interviewSubmitLabel = { textContent: '' };
  vm.runInContext(wiring.slice(wiring.indexOf('let failedInterviewMessage ='),
    wiring.indexOf("interviewForm.addEventListener('submit'"))
    + '\nglobalThis.wiringSubject = {submitCurrentInterviewAnswer};', h.context);
  const raw = '  Первая строка\nВторая строка  ';
  draft(h, raw);
  const sending = h.context.wiringSubject.submitCurrentInterviewAnswer();
  const newer = raw + '\nНовый черновик'; draft(h, newer);
  h.setFetch(async (_url, options) => {
    if (!options?.method) return json(h.runtime);
    const body = JSON.parse(options.body);
    assert.equal(body.content, raw.trim());
    return json({ turn: addTurn(h.runtime, body) });
  });
  heldImport.resolve(h.subject); await sending;
  assert.equal(h.textarea.value, newer);
  assert.equal(h.storage.get('agent4k.assessmentDraft:cycle-a:as-a'), newer);
  assert.equal(postCalls(h).length, 1);
});
