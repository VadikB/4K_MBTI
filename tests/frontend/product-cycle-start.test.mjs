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
