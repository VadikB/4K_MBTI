import assert from 'node:assert/strict';
import test from 'node:test';
import { createInterviewHarness } from './helpers/p3-a-interview.mjs';

// EXEC-03 draft regression suite. Uses production function slices via the existing
// harness. HTTP is mocked here; actual HTTP/PostgreSQL/browser evidence remains
// required separately. When moving into tests/frontend, change the import above
// to './helpers/p3-a-interview.mjs'. No production helper changes are required.
const LEGACY = 'agent4k.assessmentDraft:cycle-a:as-a';
const PENDING = 'agent4k.assessmentPending:cycle-a:as-a:8';
const ASK1 = '00000000-0000-4000-8000-000000000098';
const ASK2 = '00000000-0000-4000-8000-000000000096';
const QUESTION = '00000000-0000-4000-8000-000000000097';
const json = (value, status = 200) => new Response(JSON.stringify(value), {
  status, headers: { 'Content-Type': 'application/json' },
});
const tick = async () => { for (let index = 0; index < 30; index += 1) await Promise.resolve(); };
const deferred = () => {
  let resolve; const promise = new Promise((yes) => { resolve = yes; });
  return { promise, resolve };
};
const ask = (h, id = ASK1) => {
  const runtime = h.snapshot();
  runtime.current_situation.status = 'scenario_ended';
  runtime.clarification = { id, status: 'ASK', question_turn_id: QUESTION,
    question: { text: id === ASK1 ? 'Первое уточнение' : 'Следующее уточнение' } };
  return runtime;
};
const setup = ({ storage = new Map(), ownerId = 8, clarificationId = null } = {}) => {
  const h = createInterviewHarness({ storage });
  h.state.pendingUser = { id: ownerId };
  h.subject.initInterview();
  h.runtime = clarificationId ? ask(h, clarificationId) : h.snapshot();
  h.subject.renderProductRuntime(h.runtime);
  h.flush();
  return h;
};
const input = (h, text) => {
  h.textarea.value = text;
  h.textarea.listeners.get('input')();
};
const postCalls = (h) => h.fetchCalls.filter(([, options]) => options?.method === 'POST');
const statusCalls = (h) => h.fetchCalls.filter(([url]) => String(url).includes('/answer-status?'));
const storedValues = (h) => [...h.storage].flatMap(([key, value]) => {
  try { return [{ key, value: JSON.parse(value) }]; } catch { return []; }
});
const makeUnknown = (h, text) => {
  input(h, text);
  const operation = h.subject.prepareProductInterviewAnswer(text.trim(), text);
  // Model a persisted operation after dispatch and before any receipt. This
  // does not simulate a successful POST; HTTP/PG tests exercise real commits.
  const persisted = JSON.parse(h.storage.get(PENDING));
  persisted.status = 'unknown';
  h.storage.set(PENDING, JSON.stringify(persisted));
  return { ...operation, status: 'unknown' };
};
const status = (operation, outcome = 'absent', processing = null) => ({
  status: outcome,
  cycle_id: operation.cycleId,
  assessment_situation_id: operation.situationId,
  request_id: operation.requestId,
  turn_id: operation.turnId,
  clarification_id: operation.clarificationId,
  processing_status: processing,
  ...(outcome === 'accepted' ? { turn: {
    turn_id: operation.turnId, request_id: operation.requestId,
    content_text: operation.text, speaker_type: 'assessee',
  } } : {}),
});
const assertOriginalStatusQuery = (h, operation) => {
  assert.ok(statusCalls(h).length > 0, 'owner answer-status is read before resolving the unknown operation');
  for (const [url] of statusCalls(h)) {
    const parsed = new URL(url, 'http://owned.invalid');
    assert.equal(parsed.searchParams.get('request_id'), operation.requestId);
    assert.equal(parsed.searchParams.get('turn_id'), operation.turnId);
    assert.equal(parsed.searchParams.get('clarification_id'), operation.clarificationId);
    assert.equal(parsed.pathname, '/users/assessment/m5/situations/' + operation.situationId + '/answer-status');
  }
};
const recoverExisting = async (h, operation) => {
  // Support both automatic reload reconciliation and explicit retry as entry
  // points. Never submit the old text after its operation has already retired.
  await tick();
  const pending = h.subject.readProductInterviewAnswer();
  if (pending?.requestId === operation.requestId) {
    await h.subject.sendProductInterviewAnswer(operation.text, {
      scope: operation, draftValue: operation.draftValue,
    });
  }
  await tick();
};

test('EXEC-03 ordinary unsent draft is not retargeted into a presented M7 ASK', () => {
  const h = setup();
  const original = '  Ответ на ситуацию\nЕщё одна строка  ';
  input(h, original);
  h.subject.renderProductRuntime(ask(h));
  assert.equal(h.textarea.value, '', 'a new question starts with its own draft');
  assert.equal(h.storage.get(LEGACY), original, 'the unrelated unsent ordinary draft is retained');
  assert.equal(h.controls.submit.disabled, false, 'presented current ASK remains usable');
  assert.equal(postCalls(h).length, 0);
});

test('EXEC-03 each M7 ASK restores only its own exact raw draft after replacement and reload', () => {
  const h = setup({ clarificationId: ASK1 });
  const first = '  Черновик первого уточнения\nс пробелами  ';
  input(h, first);
  h.subject.renderProductRuntime(ask(h, ASK2));
  assert.equal(h.textarea.value, '');
  const second = 'Черновик следующего вопроса';
  input(h, second);
  const restoredFirst = setup({ storage: h.storage, clarificationId: ASK1 });
  assert.equal(restoredFirst.textarea.value, first);
  const restoredSecond = setup({ storage: h.storage, clarificationId: ASK2 });
  assert.equal(restoredSecond.textarea.value, second);
  assert.equal(postCalls(restoredFirst).length + postCalls(restoredSecond).length, 0);
});

test('EXEC-03 ordinary and ASK drafts are separated by account on the same Cycle/AS', () => {
  for (const clarificationId of [null, ASK1]) {
    const h = setup({ clarificationId });
    input(h, 'Черновик владельца 8');
    const foreign = setup({ storage: h.storage, ownerId: 9, clarificationId });
    assert.equal(foreign.textarea.value, '', 'owner 9 cannot inherit owner 8 draft');
    input(foreign, 'Новый черновик владельца 9');
    const returned = setup({ storage: h.storage, ownerId: 8, clarificationId });
    assert.notEqual(returned.textarea.value, 'Новый черновик владельца 9');
  }
});

test('EXEC-03 legacy ordinary draft migrates on confirmed ordinary readback and gains owner isolation', () => {
  const raw = '  Старый обычный draft\nбез companion metadata  ';
  const storage = new Map([[LEGACY, raw]]);
  const current = setup({ storage });
  assert.equal(current.textarea.value, raw);
  const reloaded = setup({ storage });
  assert.equal(reloaded.textarea.value, raw, 'ordinary legacy compatibility survives reload');
  const other = setup({ storage, ownerId: 9 });
  assert.equal(other.textarea.value, '', 'migration binds the draft to the confirmed owner');
});

test('EXEC-03 a legacy ordinary draft is not migrated into an initial ASK', () => {
  const raw = 'Старый ответ на основной сценарий';
  const h = setup({ storage: new Map([[LEGACY, raw]]), clarificationId: ASK1 });
  assert.equal(h.textarea.value, '');
  assert.equal(h.storage.get(LEGACY), raw, 'legacy ordinary text remains recoverable in its source scope');
});

test('EXEC-03 authoritative absence after phase change retires old operation and clears only its matching draft', async () => {
  const h = setup();
  const original = makeUnknown(h, '  Не дошедший до сервера обычный ответ  ');
  const held = deferred();
  const current = ask(h, ASK1);
  h.setFetch(async (url) => String(url).includes('/answer-status?') ? held.promise : json(current));
  h.subject.renderProductRuntime(current);
  const recovering = recoverExisting(h, original);
  await tick();
  input(h, '  Новый собственный ввод для текущего ASK\nне удалять  ');
  held.resolve(json(status(original)));
  await recovering;
  assertOriginalStatusQuery(h, original);
  assert.equal(postCalls(h).length, 0, 'phase change cannot send the old command into any endpoint');
  assert.equal(h.subject.readProductInterviewAnswer(), null, 'old operation no longer blocks the current question');
  assert.equal(h.controls.submit.disabled, false);
  assert.equal(h.storage.has(LEGACY), false, 'only the matching old ordinary draft is cleared');
  assert.equal(h.textarea.value, '  Новый собственный ввод для текущего ASK\nне удалять  ');
  assert.ok(storedValues(h).some(({ value }) => value?.requestId === original.requestId
    && value.turnId === original.turnId && value.endpoint === original.endpoint
    && value.status === 'superseded'), 'the retired command retains its identity in a resolved archive');
});

test('EXEC-03 authoritative absence for superseded ASK retires only that question operation and draft', async () => {
  const h = setup({ clarificationId: ASK1 });
  const original = makeUnknown(h, '  Ответ на прежнее уточнение\nстарый scope  ');
  const held = deferred();
  const next = ask(h, ASK2);
  h.setFetch(async (url) => String(url).includes('/answer-status?') ? held.promise : json(next));
  h.subject.renderProductRuntime(next);
  const recovering = recoverExisting(h, original);
  await tick();
  input(h, 'Новый draft второго уточнения');
  held.resolve(json(status(original)));
  await recovering;
  assertOriginalStatusQuery(h, original);
  assert.equal(postCalls(h).length, 0);
  assert.equal(h.subject.readProductInterviewAnswer(), null);
  assert.equal(h.controls.submit.disabled, false);
  assert.equal(h.textarea.value, 'Новый draft второго уточнения');
  const restoredNext = setup({ storage: h.storage, clarificationId: ASK2 });
  assert.equal(restoredNext.textarea.value, 'Новый draft второго уточнения');
  const restoredOld = setup({ storage: h.storage, clarificationId: ASK1 });
  assert.equal(restoredOld.textarea.value, '', 'the absent superseded question clears only its matching old draft');
});

test('EXEC-03 accepted applied readback clears pending while keeping newer input without another POST', async () => {
  const h = setup();
  const original = makeUnknown(h, '  Принятый исходный ответ\nиз старого запроса  ');
  const held = deferred();
  h.setFetch(async (url) => String(url).includes('/answer-status?') ? held.promise : json(h.runtime));
  const recovering = recoverExisting(h, original);
  await tick();
  input(h, '  Более новый собственный draft\nпоявился при readback  ');
  held.resolve(json(status(original, 'accepted', 'applied')));
  await recovering;
  assertOriginalStatusQuery(h, original);
  assert.equal(postCalls(h).length, 0);
  assert.equal(h.subject.readProductInterviewAnswer(), null);
  assert.equal(h.textarea.value, '  Более новый собственный draft\nпоявился при readback  ');
  assert.equal(h.storage.get(LEGACY), '  Более новый собственный draft\nпоявился при readback  ');
  assert.equal(h.controls.submit.disabled, false);
});

test('EXEC-03 failed answer-status keeps unknown identity and retry endpoint after the ASK changes', async () => {
  const h = setup({ clarificationId: ASK1 });
  const original = makeUnknown(h, 'Ответ на прежний ASK');
  const next = ask(h, ASK2);
  h.setFetch(async (url) => String(url).includes('/answer-status?') ? json({}, 503) : json(next));
  h.subject.renderProductRuntime(next);
  await recoverExisting(h, original);
  assertOriginalStatusQuery(h, original);
  assert.equal(postCalls(h).length, 0);
  const unresolved = h.subject.readProductInterviewAnswer();
  assert.equal(unresolved.requestId, original.requestId);
  assert.equal(unresolved.turnId, original.turnId);
  assert.equal(unresolved.clarificationId, ASK1);
  assert.equal(unresolved.endpoint, '/users/assessment/m7/clarifications/' + ASK1 + '/answers');
  assert.equal(unresolved.accepted, false);
  assert.equal(h.controls.submit.disabled, true, 'failed authoritative readback cannot unlock a blind fresh command');
  const restored = setup({ storage: h.storage, clarificationId: ASK2 });
  const afterReload = restored.subject.readProductInterviewAnswer();
  assert.equal(afterReload.requestId, original.requestId);
  assert.equal(afterReload.endpoint, original.endpoint);
  assert.notEqual(restored.textarea.value, original.draftValue, 'old ASK text is never a draft for the replacement ASK');
});

test('EXEC-03 same-phase authoritative absence retries M7 with the original full identity', async () => {
  const h = setup({ clarificationId: ASK1 });
  const original = makeUnknown(h, '  Повторяем ответ на тот же ASK\nпосле отсутствия  ');
  const current = h.runtime;
  h.setFetch(async (url, options) => {
    if (String(url).includes('/answer-status?')) return json(status(original));
    if (!options?.method) return json(current);
    assert.equal(url, original.endpoint);
    const body = JSON.parse(options.body);
    assert.equal(body.request_id, original.requestId);
    assert.equal(body.turn_id, original.turnId);
    assert.equal(body.content, original.text);
    current.trace.turns.push({ turn_id: body.turn_id, request_id: body.request_id,
      content_text: body.content, speaker_type: 'assessee', sequence_no: 1 });
    current.clarification.response_outcome = 'answered';
    return json({ id: ASK1, answer_turn_id: body.turn_id,
      response_request_id: body.request_id, response_outcome: 'answered' });
  });
  await recoverExisting(h, original);
  assertOriginalStatusQuery(h, original);
  assert.equal(postCalls(h).length, 1);
  assert.equal(current.trace.turns.length, 1);
  assert.equal(h.subject.readProductInterviewAnswer(), null);
});
