import assert from 'node:assert/strict';
import test from 'node:test';

import {
  advanceSessionGeneration,
  ApiResponseError,
  createSessionAwareFetch,
  readApiResponse,
  registerUnauthorizedResponseHandler,
  StaleApiResponseError,
} from '../../web/js/api.js';

const unauthorizedResponse = (detail = 'Admin session not found') =>
  new Response(JSON.stringify({ detail }), {
    status: 401,
    headers: { 'content-type': 'application/json' },
  });

test('a rejected login preserves the server error without expired-session recovery', async () => {
  let recoveries = 0;
  registerUnauthorizedResponseHandler(() => {
    recoveries += 1;
  });

  await assert.rejects(
    readApiResponse(unauthorizedResponse('Неверный пароль.'), 'Fallback', { recoverUnauthorized: false }),
    (error) => error instanceof ApiResponseError && error.status === 401 && error.message === 'Неверный пароль.',
  );
  await Promise.resolve();

  assert.equal(recoveries, 0);
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

test('a late 401 from an earlier session generation does not recover the current session', async () => {
  let releaseRequest;
  let recoveries = 0;
  const trackedFetch = createSessionAwareFetch(
    () =>
      new Promise((resolve) => {
        releaseRequest = () => resolve(unauthorizedResponse('Old session'));
      }),
  );
  registerUnauthorizedResponseHandler(() => {
    recoveries += 1;
  });

  const pendingResponse = trackedFetch('/protected');
  advanceSessionGeneration();
  releaseRequest();
  const response = await pendingResponse;

  await assert.rejects(
    readApiResponse(response, 'Fallback'),
    (error) => error instanceof StaleApiResponseError,
  );
  await Promise.resolve();

  assert.equal(recoveries, 0);
});

test('a late successful response cannot overwrite a newer session', async () => {
  let releaseRequest;
  const trackedFetch = createSessionAwareFetch(
    () =>
      new Promise((resolve) => {
        releaseRequest = () =>
          resolve(
            new Response(JSON.stringify({ user: { id: 'account-a' } }), {
              status: 200,
              headers: { 'content-type': 'application/json' },
            }),
          );
      }),
  );

  const pendingResponse = trackedFetch('/protected');
  advanceSessionGeneration();
  releaseRequest();

  await assert.rejects(
    readApiResponse(await pendingResponse, 'Fallback'),
    (error) => error instanceof StaleApiResponseError,
  );
});

test('an unfinished old recovery does not suppress recovery for the current generation', async () => {
  const recoveryResolvers = [];
  let recoveries = 0;
  registerUnauthorizedResponseHandler(
    () =>
      new Promise((resolve) => {
        recoveries += 1;
        recoveryResolvers.push(resolve);
      }),
  );

  await assert.rejects(readApiResponse(unauthorizedResponse(), 'Fallback'), ApiResponseError);
  await Promise.resolve();
  assert.equal(recoveries, 1);

  advanceSessionGeneration();
  await assert.rejects(readApiResponse(unauthorizedResponse(), 'Fallback'), ApiResponseError);
  await Promise.resolve();
  assert.equal(recoveries, 2);

  recoveryResolvers.forEach((resolve) => resolve());
});
