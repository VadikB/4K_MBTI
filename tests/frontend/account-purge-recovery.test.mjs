import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import test from 'node:test';
import {
  ApiResponseError, accountPurgeErrorMessage, confirmAccountPurge, executeAccountPurge,
  getPendingAccountPurges,
} from '../../web/js/api.js';

const storage = () => {
  const values = new Map();
  return { getItem: (key) => values.get(key) ?? null, setItem: (key, value) => values.set(key, value) };
};
const confirmed = (changes = {}) => confirmAccountPurge({ actorId: 1, targetUserId: 20,
  email: 'owned@example.test', fingerprint: 'fingerprint-a', ...changes });
const reply = (body, status = 200) => new Response(JSON.stringify(body), {
  status, headers: { 'content-type': 'application/json' },
});

test('lost reply and module reload retain exact actor/target/fingerprint/operation, without preview', async () => {
  globalThis.localStorage = storage();
  const operation = confirmed();
  const calls = [];
  globalThis.fetch = async (url, options) => {
    calls.push({ url, command: JSON.parse(options.body) });
    throw new TypeError('Failed to fetch');
  };
  await assert.rejects(executeAccountPurge(operation, { actorId: 1 }), (error) => error.outcomeUnknown);
  assert.equal(getPendingAccountPurges(1)[0].status, 'unknown');
  assert.deepEqual(getPendingAccountPurges(2), []);
  assert.throws(() => confirmed({ fingerprint: 'changed' }), (error) => error.outcomeUnknown);
  const reloaded = await import('../../web/js/api.js?purge-reloaded');
  const recovered = reloaded.getPendingAccountPurges(1)[0];
  assert.equal(recovered.operationId, operation.operationId);
  globalThis.fetch = async (url, options) => {
    calls.push({ url, command: JSON.parse(options.body) });
    return reply({ ok: true, operation_id: recovered.operationId, idempotent: true });
  };
  await reloaded.executeAccountPurge(recovered, { actorId: 1 });
  assert.deepEqual(calls[0], calls[1]);
  assert.ok(calls.every(({ url }) => !url.includes('preview')));
  assert.deepEqual(reloaded.getPendingAccountPurges(1), []);
});

for (const [status, detail] of [[403, 'Superadmin access required'], [409, 'PURGE_PREVIEW_STALE']]) {
  test(`definite ${status} refusal restores new preview/confirmation and never leaks raw text`, async () => {
    globalThis.localStorage = storage();
    const operation = confirmed();
    globalThis.fetch = async () => reply({ detail }, status);
    let failure;
    try { await executeAccountPurge(operation, { actorId: 1 }); } catch (error) { failure = error; }
    assert.ok(failure instanceof ApiResponseError);
    assert.equal(failure.outcomeUnknown, false);
    assert.equal(getPendingAccountPurges(1).length, 0);
    assert.notEqual(confirmed().operationId, operation.operationId);
    assert.doesNotMatch(accountPurgeErrorMessage(failure), /Superadmin access required|Failed to fetch/);
  });
}

test('5xx/invalid response remains unknown; a later denied recovery cannot erase prior uncertainty', async () => {
  globalThis.localStorage = storage();
  const operation = confirmed();
  globalThis.fetch = async () => reply({ detail: 'SQL secret traceback' }, 503);
  await assert.rejects(executeAccountPurge(operation, { actorId: 1 }), (error) =>
    error.outcomeUnknown && !/SQL|secret|traceback/.test(error.message));
  globalThis.fetch = async () => reply({ detail: 'Superadmin access required' }, 403);
  await assert.rejects(executeAccountPurge(getPendingAccountPurges(1)[0], { actorId: 1 }), (error) => error.outcomeUnknown);
  assert.equal(getPendingAccountPurges(1)[0].operationId, operation.operationId);
});

test('changed actor, target, fingerprint and command cannot reuse confirmation', async () => {
  globalThis.localStorage = storage();
  const operation = confirmed();
  let calls = 0;
  globalThis.fetch = async () => { calls += 1; throw new Error('must not send'); };
  for (const [altered, actorId] of [
    [operation, 2], [{ ...operation, targetUserId: 21 }, 1],
    [{ ...operation, fingerprint: 'new-fingerprint' }, 1], [{ ...operation, email: 'other@example.test' }, 1],
  ]) await assert.rejects(executeAccountPurge(altered, { actorId }));
  assert.equal(calls, 0);
  const other = confirmed({ targetUserId: 21, email: 'other@example.test' });
  assert.notEqual(other.operationId, operation.operationId);
});

test('blocked persistence prevents sending an unrecoverable delete', async () => {
  globalThis.localStorage = { getItem: () => null, setItem: () => { throw new Error('quota'); } };
  assert.throws(() => confirmed(), (error) => error.code === 'PURGE_RECOVERY_STORAGE_UNAVAILABLE');
});

const wiring = fs.readFileSync('web/js/wiring.js', 'utf8');
const start = wiring.indexOf("    if (['purge-account', 'recover-purge-account'].includes(button.dataset.action)) {");
const end = wiring.indexOf('    if (!organizationId)', start);
const handler = wiring.slice(start, end);
const click = async ({ module, action = 'purge-account', state = { pendingUser: { id: 1 } } }) => {
  const button = { dataset: { action, userId: '20', email: 'owned@example.test' }, disabled: false };
  const alerts = [];
  vm.runInNewContext('(function () {' + handler + '})()', {
    button, state, loadAdminOrganizations: async () => module, accountPurgeErrorMessage,
    window: { alert: (message) => alerts.push(message), prompt: () => 'owned@example.test', confirm: () => true },
  });
  await new Promise((resolve) => setTimeout(resolve, 10));
  assert.equal(button.disabled, false);
  return alerts;
};

test('actual production click catches preview transport failure locally', async () => {
  const messages = [];
  await click({ module: {
    pendingAdminAccountPurges: () => [], previewAdminAccountPurge: async () => { throw new TypeError('Failed to fetch'); },
    showAdminAccountPurgeError: (error, phase) => messages.push(accountPurgeErrorMessage(error, { phase })),
  } });
  assert.equal(messages.length, 1);
  assert.match(messages[0], /Не удалось получить состав/);
  assert.doesNotMatch(messages[0], /Failed to fetch/);
});

test('actual production click recovers an old target before preview, including dedicated recovery control', async () => {
  for (const action of ['purge-account', 'recover-purge-account']) {
    const calls = [];
    await click({ action, module: {
      pendingAdminAccountPurges: () => [{ targetUserId: 20 }],
      previewAdminAccountPurge: async () => { calls.push('preview'); throw new Error('deleted target'); },
      recoverAdminAccountPurge: async (id) => calls.push(['recover', id]),
    } });
    assert.deepEqual(calls, [['recover', 20]]);
  }
});

test('actual production click catches execute rejection and suppresses old actor preview failure', async () => {
  const messages = [];
  await click({ module: {
    pendingAdminAccountPurges: () => [], previewAdminAccountPurge: async () => ({ fingerprint: 'a' }),
    purgeAdminAccount: async () => { throw new TypeError('Failed to fetch'); },
    showAdminAccountPurgeError: (error, phase) => messages.push({ phase, message: accountPurgeErrorMessage(error, { phase }) }),
  } });
  assert.equal(messages[0].phase, 'execute');
  assert.doesNotMatch(messages[0].message, /Failed to fetch/);
  const state = { pendingUser: { id: 1 } };
  await click({ state, module: {
    pendingAdminAccountPurges: () => [], previewAdminAccountPurge: async () => {
      state.pendingUser.id = 2;
      throw new TypeError('Failed to fetch');
    }, showAdminAccountPurgeError: () => messages.push('stale'),
  } });
  assert.equal(messages.length, 1);
});

test('post-commit failure code cannot erase command or claim rollback; exact receipt retry resolves', async () => {
  globalThis.localStorage = storage();
  const operation = confirmed();
  globalThis.fetch = async () => reply({ detail: 'PURGE_EXECUTION_FAILED' }, 409);
  await assert.rejects(executeAccountPurge(operation, { actorId: 1 }), (error) =>
    error.outcomeUnknown && !/отменено|не выполнено/.test(error.message));
  assert.equal(getPendingAccountPurges(1)[0].operationId, operation.operationId);
  globalThis.fetch = async (_url, options) => reply({ ok: true,
    operation_id: JSON.parse(options.body).operation_id, idempotent: true });
  await executeAccountPurge(getPendingAccountPurges(1)[0], { actorId: 1 });
  assert.equal(getPendingAccountPurges(1).length, 0);
});

test('storage read/write failure resuming an old unknown command never claims that delete was not sent', async () => {
  for (const fail of ['read', 'write']) {
    globalThis.localStorage = storage();
    const operation = confirmed();
    globalThis.fetch = async () => { throw new TypeError('Failed to fetch'); };
    await assert.rejects(executeAccountPurge(operation, { actorId: 1 }), (error) => error.outcomeUnknown);
    const unknown = getPendingAccountPurges(1)[0];
    globalThis.localStorage[fail === 'read' ? 'getItem' : 'setItem'] = () => { throw new Error('storage denied'); };
    let requests = 0;
    globalThis.fetch = async () => { requests += 1; throw new Error('must not send'); };
    await assert.rejects(executeAccountPurge(unknown, { actorId: 1 }), (error) =>
      error.outcomeUnknown && /Исход операции пока неизвестен/.test(accountPurgeErrorMessage(error)) &&
      !/Удаление не отправлено|отменено|не выполнено/.test(error.message));
    assert.equal(requests, 0);
  }
});

for (const fail of ['read', 'write']) {
  test(`F02/R01 success receipt survives ${fail} failure during local cleanup and reload checks the same operation`, async () => {
    const backing = storage();
    globalThis.localStorage = backing;
    const operation = confirmed();
    const commands = [];
    const original = backing[fail === 'read' ? 'getItem' : 'setItem'];
    globalThis.fetch = async (_url, options) => {
      commands.push(JSON.parse(options.body));
      backing[fail === 'read' ? 'getItem' : 'setItem'] = () => { throw new Error('storage denied after server success'); };
      return reply({ ok: true, deleted: true, operation_id: operation.operationId });
    };
    const receipt = await executeAccountPurge(operation, { actorId: 1 });
    assert.equal(receipt.ok, true);
    assert.equal(receipt.operation_id, operation.operationId);
    assert.deepEqual(getPendingAccountPurges(1), []);
    assert.equal(await executeAccountPurge(operation, { actorId: 1 }), receipt);
    assert.equal(commands.length, 1, 'the known receipt never sends a second request in the same session');
    backing[fail === 'read' ? 'getItem' : 'setItem'] = original;
    const reloaded = await import(`../../web/js/api.js?purge-cleanup-${fail}`);
    const recovered = reloaded.getPendingAccountPurges(1)[0];
    assert.equal(recovered.operationId, operation.operationId);
    globalThis.fetch = async (_url, options) => {
      commands.push(JSON.parse(options.body));
      return reply({ ok: true, deleted: true, operation_id: operation.operationId, idempotent: true });
    };
    assert.equal((await reloaded.executeAccountPurge(recovered, { actorId: 1 })).idempotent, true);
    assert.deepEqual(commands[0], commands[1]);
    assert.deepEqual(reloaded.getPendingAccountPurges(1), []);
  });
}

for (const [code, status, expected] of [
  ['CANNOT_PURGE_CONFIGURED_ACCOUNT', 409, /защищён настройками/],
  ['CANNOT_PURGE_LAST_ORGANIZATION_ADMIN', 409, /последнего администратора/],
  ['ACCOUNT_PURGE_SCOPE_FORBIDDEN', 403, /всех связанных данных/],
]) {
  test(`F02 explicit ${code} refusal is actionable and never shown as deletion success`, async () => {
    globalThis.localStorage = storage();
    const operation = confirmed();
    globalThis.fetch = async () => reply({ detail: code }, status);
    await assert.rejects(executeAccountPurge(operation, { actorId: 1 }), (error) => {
      assert.match(accountPurgeErrorMessage(error), expected);
      assert.equal(error.outcomeUnknown, false);
      return true;
    });
    assert.deepEqual(getPendingAccountPurges(1), []);
  });
}
