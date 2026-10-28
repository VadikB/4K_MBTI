import assert from 'node:assert/strict';
import test from 'node:test';
import { fetchWithDeadline, readApiResponse } from '../../web/js/api.js';

test('HTTP deadline bounds a stalled response body and aborts transport', async () => {
  const original = globalThis.fetch;
  let signal;
  globalThis.fetch = async (_url, options) => {
    signal = options.signal;
    return { text: () => new Promise(() => {}) };
  };
  try {
    await assert.rejects(fetchWithDeadline('/synthetic', {}, 10), { name: 'RequestDeadlineError' });
    assert.equal(signal.aborted, true);
  } finally { globalThis.fetch = original; }
});

test('HTTP deadline retains status/body and rejects invalid JSON without hanging', async () => {
  const original = globalThis.fetch;
  try {
    globalThis.fetch = async () => new Response('{"detail":"conflict"}', { status: 409 });
    await assert.rejects(readApiResponse(await fetchWithDeadline('/synthetic'), 'failed'), { status: 409, message: 'conflict' });
    globalThis.fetch = async () => new Response('invalid json');
    await assert.rejects(readApiResponse(await fetchWithDeadline('/synthetic'), 'invalid body'), /invalid body/);
  } finally { globalThis.fetch = original; }
});
