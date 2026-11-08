import test from 'node:test';
import assert from 'node:assert/strict';

globalThis.window = { fetch: globalThis.fetch };
const { startPreparedProductCycle } = await import('../../web/js/product-cycle-start.js');

const jsonResponse = (value, status = 200) => new Response(JSON.stringify(value), {
  status, headers: { 'Content-Type': 'application/json' },
});

test('returns the committed first runtime after the start POST response is lost', async () => {
  const calls = [];
  const fetchImpl = async (url, options) => {
    calls.push([url, options]);
    if (calls.length === 1) throw new TypeError('Failed to fetch');
    return jsonResponse({ cycle_id: 'cycle-1', status: { collection_status: 'active' },
      current_situation: { status: 'active', participant_payload: { title: 'Synthetic AS' } } });
  };
  const result = await startPreparedProductCycle('cycle-1', { fetchImpl, operationId: 'start-1' });
  assert.equal(result.recovered_after_transport_failure, true);
  assert.equal(result.runtime.current_situation.participant_payload.title, 'Synthetic AS');
  assert.equal(calls.length, 2);
  assert.match(calls[1][0], /\/cycles\/cycle-1\/runtime$/);
});

test('does not present an admitted but unstarted situation as a successful start', async () => {
  const fetchImpl = async (url) => url.endsWith('/start')
    ? Promise.reject(new TypeError('Failed to fetch'))
    : jsonResponse({ cycle_id: 'cycle-1', status: { collection_status: 'prepared' },
      current_situation: { status: 'admitted' } });
  await assert.rejects(
    startPreparedProductCycle('cycle-1', { fetchImpl, operationId: 'start-2' }),
    (error) => error.name === 'AssessmentStartUnknown' && error.operationId === 'start-2',
  );
});

test('does not turn a server rejection into an unknown transport outcome', async () => {
  const fetchImpl = async () => jsonResponse({ detail: 'ASSIGNMENT_CANCELLED' }, 409);
  await assert.rejects(
    startPreparedProductCycle('cycle-1', { fetchImpl, operationId: 'start-3' }),
    (error) => error.status === 409,
  );
});

test('preserves an unknown start across failed readback and recovers by GET after reload', async () => {
  const values = new Map();
  globalThis.window.sessionStorage = {
    getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, value),
    removeItem: (key) => values.delete(key),
  };
  const firstCalls = [];
  const firstFetch = async (url, options) => {
    firstCalls.push([url, options]);
    if (url.endsWith('/start')) throw new TypeError('Failed to fetch');
    return jsonResponse({ detail: 'temporarily unavailable' }, 503);
  };
  await assert.rejects(startPreparedProductCycle('cycle-1', { fetchImpl: firstFetch, operationId: 'start-4' }),
    (error) => error.name === 'AssessmentStartUnknown' && error.operationId === 'start-4');
  assert.equal(firstCalls.length, 2);
  const reloadCalls = [];
  const reloadFetch = async (url, options) => {
    reloadCalls.push([url, options]);
    return jsonResponse({ cycle_id: 'cycle-1', status: { collection_status: 'active' },
      current_situation: { status: 'active', participant_payload: { title: 'Synthetic AS' } } });
  };
  const recovered = await startPreparedProductCycle('cycle-1', { fetchImpl: reloadFetch, operationId: 'start-5' });
  assert.equal(recovered.recovered_after_transport_failure, true);
  assert.equal(reloadCalls.length, 1);
  assert.match(reloadCalls[0][0], /\/runtime$/);
  assert.equal(values.size, 0);
  delete globalThis.window.sessionStorage;
});

test('an explicit retry after unstarted readback reuses the original idempotency key', async () => {
  const values = new Map();
  globalThis.window.sessionStorage = {
    getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, value),
    removeItem: (key) => values.delete(key),
  };
  const firstFetch = async (url) => url.endsWith('/start')
    ? Promise.reject(new TypeError('Failed to fetch'))
    : jsonResponse({ cycle_id: 'cycle-1', current_situation: { status: 'admitted' } });
  await assert.rejects(startPreparedProductCycle('cycle-1', { fetchImpl: firstFetch, operationId: 'start-6' }),
    (error) => error.name === 'AssessmentStartUnknown');
  const calls = [];
  const retryFetch = async (url, options) => {
    calls.push([url, options]);
    if (url.endsWith('/runtime')) return jsonResponse({ cycle_id: 'cycle-1', current_situation: { status: 'admitted' } });
    return jsonResponse({ plan: { cycle_id: 'cycle-1' }, runtime: { cycle_id: 'cycle-1' } }, 201);
  };
  await startPreparedProductCycle('cycle-1', { fetchImpl: retryFetch, operationId: 'start-7' });
  assert.equal(calls.length, 2);
  assert.equal(JSON.parse(calls[1][1].body).idempotency_key, 'start-6');
  assert.equal(values.size, 0);
  delete globalThis.window.sessionStorage;
});

test('foreign runtime cannot confirm a lost start', async () => {
  const fetchImpl = async (url) => url.endsWith('/start')
    ? Promise.reject(new TypeError('Failed to fetch'))
    : jsonResponse({ cycle_id: 'other-cycle', current_situation: {
      status: 'active', participant_payload: { title: 'Foreign AS' },
    } });
  await assert.rejects(startPreparedProductCycle('cycle-1', { fetchImpl, operationId: 'start-8' }),
    (error) => error.name === 'AssessmentStartUnknown');
});

test('a 503 POST response also requires readback before reporting failure', async () => {
  const calls = [];
  const fetchImpl = async (url) => {
    calls.push(url);
    if (url.endsWith('/start')) return jsonResponse({ detail: 'temporary error' }, 503);
    return jsonResponse({ cycle_id: 'cycle-1', current_situation: {
      status: 'active', participant_payload: { title: 'Persisted AS' },
    } });
  };
  const result = await startPreparedProductCycle('cycle-1', { fetchImpl, operationId: 'start-9' });
  assert.equal(result.recovered_after_transport_failure, true);
  assert.equal(calls.length, 2);
});
