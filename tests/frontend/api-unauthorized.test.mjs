import assert from 'node:assert/strict';
import test from 'node:test';

import {
  ApiResponseError,
  readApiResponse,
  registerUnauthorizedResponseHandler,
} from '../../web/js/api.js';

const unauthorizedResponse = (detail = 'Admin session not found') =>
  new Response(JSON.stringify({ detail }), {
    status: 401,
    headers: { 'content-type': 'application/json' },
  });

test('a protected API 401 starts expired-session recovery and preserves the status', async () => {
  let recoveries = 0;
  registerUnauthorizedResponseHandler(() => {
    recoveries += 1;
  });

  await assert.rejects(
    readApiResponse(unauthorizedResponse(), 'Fallback'),
    (error) => error instanceof ApiResponseError && error.status === 401,
  );
  await Promise.resolve();

  assert.equal(recoveries, 1);
});

test('concurrent 401 responses trigger only one recovery flow', async () => {
  let recoveries = 0;
  let finishRecovery;
  registerUnauthorizedResponseHandler(
    () =>
      new Promise((resolve) => {
        recoveries += 1;
        finishRecovery = resolve;
      }),
  );

  const attempts = await Promise.allSettled([
    readApiResponse(unauthorizedResponse('Admin session not found'), 'Fallback'),
    readApiResponse(unauthorizedResponse('Session not found'), 'Fallback'),
  ]);
  await Promise.resolve();

  assert.equal(recoveries, 1);
  assert.ok(attempts.every((attempt) => attempt.status === 'rejected' && attempt.reason.status === 401));
  finishRecovery();
});
